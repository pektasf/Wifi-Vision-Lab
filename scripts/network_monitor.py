import pandas as pd
from scripts.common import DATA,stamp,write_rows
def run():
 p=DATA/'device_inventory.csv'
 if not p.exists(): return []
 cur=pd.read_csv(p).fillna(''); oldp=DATA/'last_inventory.csv'; old=pd.read_csv(oldp).fillna('') if oldp.exists() else pd.DataFrame(columns=['ip'])
 a=set(old.get('ip',pd.Series(dtype=str)).astype(str)); b=set(cur.get('ip',pd.Series(dtype=str)).astype(str))
 ev=[{'timestamp':stamp(),'event':'FIRST_OBSERVED','ip':ip} for ip in sorted(b-a)]+[{'timestamp':stamp(),'event':'NOT_IN_LATEST_SCAN','ip':ip} for ip in sorted(a-b)]
 write_rows(DATA/'network_events.csv',ev,['timestamp','event','ip']); cur.to_csv(oldp,index=False); return ev
if __name__=='__main__': print(len(run()))
