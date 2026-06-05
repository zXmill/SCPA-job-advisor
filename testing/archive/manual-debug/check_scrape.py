import sys, json, re

d = json.load(sys.stdin)
jobs = d['jobs']
print('count=', d['count'])

sources = {}
for j in jobs:
    s = j['source'] or 'unknown'
    sources[s] = sources.get(s, 0) + 1
print('sources=', sources)

tech_kw = {'software','developer','engineer','devops','backend','frontend','data scientist','data engineer','cloud','sre','full-stack','fullstack','machine learning','ml engineer','python','react','java','android','ios'}
nontech_kw = {'teacher','guru','accountant','accounting','finance','financial','hr ','human resources','marketing','sales ','designer','nurse','perawat','legal','counsel','operations','logistics','customer service','customer success','content writer','copywriter','admin','secretary','supervisor'}

tech = 0
nontech = 0
other = 0
nt = []
for j in jobs:
    t = j['title'].lower()
    if any(k in t for k in nontech_kw):
        nontech += 1
        nt.append(j['title'])
    elif any(k in t for k in tech_kw):
        tech += 1
    else:
        other += 1

print('tech=', tech, 'nontech=', nontech, 'other=', other)
print('non-tech samples:')
for t in nt[:15]:
    print(' ', t)
