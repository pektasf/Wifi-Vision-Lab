from scripts.device_inventory import scan
from scripts.device_intelligence import run as intelligence
from scripts.device_classifier import run as classify
from scripts.device_history import run as history
from scripts.behavior_analysis import run as behavior
from scripts.network_topology import run as topology
from scripts.network_monitor import run as monitor
def main():
 net,devices=scan(); intelligence(); classify(); history(); behavior(); topology(); monitor()
 print(f"Scan complete: {len(devices)} observed devices on {net['network']}")
if __name__=='__main__': main()
