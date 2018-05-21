from django.shortcuts import render
from django.http import JsonResponse
from elasticsearch import Elasticsearch
from django.core.cache import cache
import time
client = Elasticsearch(host='192.168.1.110')
# Create your views here.
def index(request):
    return render(request,'index.html')

# 搜索建议
def suggest(request):
    search_word = request.GET.get('search_word')
    response = client.search(
        index='movie',
        body={
            "suggest":{
                "movie_suggest":{
                    "prefix": search_word,
                    "completion": {
                        "field":"suggest",
                        "size":5,
                        "fuzzy":{
                        # 模糊查询，编辑距离
                            "fuzziness":1
                        }
                    }
                }
            }
        }
        )
    title_list = []
    for response in response['suggest']['movie_suggest'][0]['options']:
        title_list.append(response['_source']['title'][:20])
    return JsonResponse({'suggest':title_list})

def search(request): 
    NUMS_PER_PAGE = 8
    try:
        page_num = request.GET.get('page', 1)
        page_num = int(page_num)
        
        search_word = request.GET.get('search_word')
        if len(search_word)<1:
            raise Exception('请输入关键词')
        if len(search_word)>20:
            raise Exception('关键词过长')
        start_time = time.time()
        # 使用缓存
        if not cache.get(search_word+'_'+str(page_num)):
            response = client.search(
                    index="movie",
                    body={
                        "query":{
                            "multi_match":{
                                "query":search_word,
                                "fields":["title^3", "type"]
                            }
                        },
                        "from":(page_num-1)*NUMS_PER_PAGE,
                        "size": NUMS_PER_PAGE,
                        # 高亮
                        "highlight": {
                            "pre_tags": ["<span class=\"search-word\">"],
                            "post_tags": ["</span>"],
                            "fields": {
                                "title": {},
                                "type": {},
                                "introduction": {}
                            }
                        }
                    }
                )
            result_list = []
            res = response['hits']['hits']
             # 生成download_url的元组
            def gen_list(url_list):
                try:
                    url_list += []
                except:
                    url_list = [url_list]
                return url_list
            for result in res:
                result_list.append({
                        'id': response.index(result),
                        'title': result['highlight']['title'][0] if 'title' in result['highlight'] else result['_source']['title'],
                        'type': result['highlight']['type'][0] if 'type' in result['highlight'] else result['_source']['type'],
                        'introduction': result['highlight']['introduction'][0] if 'introduction' in result['highlight'] else result['_source']['introduction'],
                        'download_url':gen_list(result['_source']['download_url']),
                        'url': result['_source']['url'],
                        'age': result['_source']['age'],
                        'douban_score': result['_source']['douban_score'],
                        'IMDb_score': result['_source']['IMDb_score'],
                        'front_img_path' :result['_source']['front_img_path']
                    })
            cache.set(search_word+'_'+str(page_num), result_list , 60)
            cache.set(str(search_word), response["hits"]["total"], 60)
        end_time = time.time()
        result_list = cache.get(search_word+'_'+str(page_num))
        search_count = cache.get(str(search_word))
        if search_count == 0:
            MAX_PAGE = 1
        else:
            MAX_PAGE = int(search_count/NUMS_PER_PAGE)+1 if \
                search_count/NUMS_PER_PAGE !=0 else int(search_count/NUMS_PER_PAGE)
        if page_num>MAX_PAGE or page_num<0:
            raise Exception('页码不符合规范')
        # 分页逻辑
        page = list(range(max(1,page_num-2), page_num)) +\
            list(range(page_num, min(page_num+2, MAX_PAGE)+1))
        if page_num <= 2:
            page = list(range(1, min(MAX_PAGE, 5)+1))
        if page_num >= MAX_PAGE-1:
            page = list(range(max(1, MAX_PAGE-4), MAX_PAGE+1))
        if page[0]-1 >= 2:
            page.insert(0, '...')
            page.insert(0, 1)
        if MAX_PAGE - page[-1] >= 2:
            page.append('...')
            page.append(MAX_PAGE)
            
    except Exception as e:
        return render(request, 'message.html')
    
    context = {}
    context['search_time'] = str(end_time - start_time)[:5]
    context['search_word'] = search_word
    context['previous'] = True if page_num-1>0 else False
    context['next'] = True if page_num+1<=MAX_PAGE else False 
    context['page_num'] = page_num
    context['page'] = page
    context['result_list'] = result_list
    context['search_count'] = search_count 
    # 实现缓存，待续?
    return render(request, 'result.html', context)
