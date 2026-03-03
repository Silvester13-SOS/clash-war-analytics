

import requests
import json
headers = {
        'Accept': 'application/json',
        'authorization': "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6ImUzOWY1OTRiLTdhZjItNDE4ZC05MGJmLTk0NzliZmZlOGQxMyIsImlhdCI6MTcyNjMxMjg2MCwic3ViIjoiZGV2ZWxvcGVyL2VhOTMxZWEzLTYxYjAtODA0MS1kZjc3LTAzZDA2ZGM3NDQ2OSIsInNjb3BlcyI6WyJjbGFzaCJdLCJsaW1pdHMiOlt7InRpZXIiOiJkZXZlbG9wZXIvc2lsdmVyIiwidHlwZSI6InRocm90dGxpbmcifSx7ImNpZHJzIjpbIjk4Ljk3LjkuMzQiXSwidHlwZSI6ImNsaWVudCJ9XX0.lP-5GwJF2uVt3Jh3ZPFA9hoL9lZJMWdPxzUV-IUZ24kHQPUVNV5WbsAttQEBSvT-zpS---koyOnqvphqlxLY2A"
}

response = requests.get('https://api.clashofclans.com/v1/clans/%23822URC/members', headers = headers)
clan_json = response.json()
test_dict = clan_json['items']

def get_name(data):
    for k,v in data.items():
        if k=='items':
            for i in v:
                yield i.get('name')
                yield i.get('tag')
        elif isinstance(v, dict):
            yield from get_name(v)

names = list(get_name(clan_json))
print(names)


# def get_vals(clan_json, items_list):
#    for i, j in clan_json.items():
#      if i in items_list:
#         yield (i, j)
#      yield from [] if not isinstance(j, dict) else get_vals(j, items_list)
 
# # initializing dictionary
# # test_dict = {'gfg': {'is': {'best' : 3}}, 'for': {'all' : 4}, 'geeks': 5}
 
# # printing original dictionary
# #print("The original dictionary is : " + str(clan_json))
 
# # initializing keys list 
# key_list = ['items']
# items_list = key_list['name', 'tag']
# print(type(items_list))
# # Extract selective keys' values [ Including Nested Keys ]
# # Using recursion + loop + yield
# res = dict(get_vals(clan_json, items_list))
 
# # printing result 
# print("The extracted values : " + str(res)) 