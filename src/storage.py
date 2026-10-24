from __future__ import annotations
import json
import sqlite3
from datetime import UTC,datetime
from pathlib import Path
class Storage:
    def __init__(self,path:str="data/drbl.sqlite3"):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self._init()
    def _connect(self):return sqlite3.connect(self.path,timeout=10)
    def _init(self):
        with self._connect() as c:
            c.execute("CREATE TABLE IF NOT EXISTS backtests (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, model TEXT NOT NULL, params_json TEXT NOT NULL, metrics_json TEXT NOT NULL, equity_json TEXT NOT NULL, trades_json TEXT NOT NULL)")
            c.execute("CREATE TABLE IF NOT EXISTS order_previews (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, payload_json TEXT NOT NULL, status TEXT NOT NULL)")
    def save_backtest(self,model:str,params:dict,metrics:dict,equity:dict,trades:list[dict])->int:
        with self._connect() as c:
            cur=c.execute("INSERT INTO backtests(created_at,model,params_json,metrics_json,equity_json,trades_json) VALUES(?,?,?,?,?,?)",(datetime.now(UTC).isoformat(),model,json.dumps(params,default=str),json.dumps(metrics,default=str),json.dumps(equity,default=str),json.dumps(trades,default=str)))
            return int(cur.lastrowid)
    def save_order_preview(self,payload:dict,status:str="PREVIEW_ONLY"):
        with self._connect() as c:c.execute("INSERT INTO order_previews(created_at,payload_json,status) VALUES(?,?,?)",(datetime.now(timezone.utc).isoformat(),json.dumps(payload,default=str),status))
