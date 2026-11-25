import subprocess,re,time,platform
from scripts.common import DATA,stamp,write_rows
def read_wifi():
 if platform.system()!='Windows': raise RuntimeError('Windows gereklidir.')
 t=subprocess.run(['netsh','wlan','show','interfaces'],capture_output=True,text=True,errors='ignore').stdout
 def v(p):
  m=re.search(p,t,re.I|re.M); return m.group(1).strip() if m else ''
 return {'timestamp':stamp(),'interface':v(r'^\s*Name\s*:\s*(.+)$'),'ssid':v(r'^\s*SSID\s*:\s*(.+)$'),'bssid':v(r'^\s*BSSID\s*:\s*(.+)$'),'radio':v(r'^\s*Radio type\s*:\s*(.+)$'),'channel':v(r'^\s*Channel\s*:\s*(.+)$'),'signal_percent':v(r'^\s*Signal\s*:\s*(.+)$'),'rx_mbps':v(r'^\s*Receive rate \(Mbps\)\s*:\s*(.+)$'),'tx_mbps':v(r'^\s*Transmit rate \(Mbps\)\s*:\s*(.+)$')}
def main():
 print('Wi-Fi logger running. Ctrl+C to stop.')
 while True:
  r=read_wifi(); write_rows(DATA/'wifi_signal_history.csv',[r],list(r)); print(r['timestamp'],'Signal',r['signal_percent'],'Channel',r['channel']); time.sleep(5)
if __name__=='__main__':
 try: main()
 except KeyboardInterrupt: print('Stopped')
