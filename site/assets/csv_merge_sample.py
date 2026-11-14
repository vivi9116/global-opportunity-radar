#!/usr/bin/env python3
"""Two CSVs, exact normalized key matching. Review ambiguous/missing keys manually.
Example: python csv_merge_sample.py --left a.csv --right b.csv --key company --out result.csv
This is a general delivery sample, not a tested solution for every scraped request.
"""
import argparse
import csv
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

def normalize(value):return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',value).strip()).casefold()
def read(path,key):
    with open(path,encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream)
        if not reader.fieldnames or key not in reader.fieldnames:raise ValueError(f'{path}: missing column {key!r}')
        return reader.fieldnames,list(reader)
def merge(left,right,key,out):
    if Path(out).resolve() in {Path(left).resolve(),Path(right).resolve()}:raise ValueError('Output must not overwrite either input.')
    lf,lr=read(left,key);rf,rr=read(right,key);index=defaultdict(list)
    for row in rr:
        normalized=normalize(row.get(key) or '')
        if normalized:index[normalized].append(row)
    fields=list(lf)+['right_'+field for field in rf]+['match_status']
    if len(fields)!=len(set(fields)):raise ValueError('Column collision: rename left columns beginning with right_ or match_status.')
    with open(out,'w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for row in lr:
            value=normalize(row.get(key) or '');matches=index.get(value,[]) if value else []
            status='missing_key' if not value else 'not_found' if not matches else 'ambiguous' if len(matches)>1 else 'matched'
            joined={**row,'match_status':status}
            if len(matches)==1:joined.update({'right_'+field:matches[0].get(field,'') for field in rf})
            writer.writerow(joined)
    return len(lr)
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for field in ['left','right','key','out']:parser.add_argument('--'+field,required=True)
    args=parser.parse_args();count=merge(args.left,args.right,args.key,args.out)
    print(f'Wrote {count} rows. Check match_status before delivery; ambiguous rows were not silently merged.')
if __name__=='__main__':main()
