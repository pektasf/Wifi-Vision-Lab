from scripts.discovery import run as discover
from scripts.device_intelligence import run as intelligence
from scripts.device_classifier import run as classify
from scripts.device_history import run as history
from scripts.behavior_analysis import run as behavior
from scripts.network_topology import run as topology
from scripts.network_monitor import run as monitor
from scripts.ap_client_intelligence import run as ap_client_run
from scripts.network_intelligence import run as infrastructure_run
from scripts.wifi_signal_intelligence import run as signal_run
def main():
 net,devices=discover()
 intelligence()
 classify()
 history()
 behavior()
 topology()
 monitor()
 try:
  ap_client_run()
 except Exception as e:
  print(f'AP-client mod?l? uyar?s?: {e}')
 for module_name, module_run in [
     ("A? altyap?s?", infrastructure_run),
     ("Wi-Fi sinyal analizi", signal_run)
 ]:
     try:
         module_run()
     except Exception as e:
         print(f"{module_name} mod?l? uyar?s?: {e}")
 print(f"Scan complete: {len(devices)} observed devices on {net['network']}")
if __name__=='__main__': main()
