import time,ipaddress
from scripts.device_inventory import get_network,ping_one
from scripts.common import DATA,stamp,write_rows
def main():
 net=get_network(); hosts=[str(x) for x in ipaddress.ip_network(net['network'],strict=False).hosts()][:512]; prev={}
 print(f"Monitoring {net['network']}; Ctrl+C to stop")
 while True:
  for ip in hosts:
   ok=ping_one(ip)
   if ip in prev and prev[ip]!=ok:
    write_rows(DATA/'live_events.csv',[{'timestamp':stamp(),'ip':ip,'event':'PING_RESPONDING' if ok else 'PING_NOT_RESPONDING'}],['timestamp','ip','event'])
   prev[ip]=ok
  time.sleep(30)
if __name__=='__main__':
 try: main()
 except KeyboardInterrupt: print('Stopped')
