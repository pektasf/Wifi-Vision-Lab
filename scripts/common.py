from pathlib import Path
import csv
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'/'processed'
LOGS=ROOT/'logs'
DATA.mkdir(parents=True,exist_ok=True); LOGS.mkdir(parents=True,exist_ok=True)
def stamp(): return datetime.now().astimezone().isoformat(timespec='seconds')
def write_rows(path,rows,fields):
 path=Path(path); exists=path.exists() and path.stat().st_size>0
 with path.open('a',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore')
  if not exists: w.writeheader()
  w.writerows(rows)
def overwrite_rows(path,rows,fields):
 with Path(path).open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); w.writeheader(); w.writerows(rows)
