import os
import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from airtable_client import is_airtable_available, get_table
from supabase_client import insert_rows, select_rows, update_rows, is_configured as is_supabase_configured

class BaseRepository(ABC):
    """
    Base repository class with dual-write and fallback-read capability.
    Primary: Supabase
    Secondary/Fallback: Airtable
    """
    
    def __init__(self, table_name: str, airtable_name: str):
        self.table_name = table_name
        self.airtable_name = airtable_name

    def _bg(self, fn, *args, **kwargs):
        t = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
        t.start()

    @abstractmethod
    def _map_to_supabase(self, data: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def _map_to_airtable(self, data: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def _map_from_supabase(self, row: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def _map_from_airtable(self, record: Dict[str, Any]) -> Dict[str, Any]:
        pass

    def get_by_id(self, chat_id: str, id_field: str = "chat_id") -> Optional[Dict[str, Any]]:
        # 1. Try Supabase
        if is_supabase_configured():
            rows, error = select_rows(self.table_name, {id_field: str(chat_id)}, limit=1)
            if not error and rows:
                return self._map_from_supabase(rows[0])

        # 2. Try Airtable
        if is_airtable_available():
            try:
                # Airtable formula for numeric or string chat id
                formula = f"{{{self._airtable_id_field()}}}={chat_id}" if str(chat_id).isdigit() else f"{{{self._airtable_id_field()}}}='{chat_id}'"
                records = get_table(self.airtable_name).all(formula=formula)
                if records:
                    return self._map_from_airtable(records[0]["fields"])
            except Exception:
                pass
        
        return None

    def upsert(self, chat_id: str, data: Dict[str, Any], id_field: str = "chat_id"):
        # We start fresh with Supabase, so we always try to write there first.
        if is_supabase_configured():
            payload = self._map_to_supabase({**data, id_field: str(chat_id)})
            self._bg(insert_rows, self.table_name, [payload], upsert=True, on_conflict=id_field)
        
        # Dual-write to Airtable for legacy support
        if is_airtable_available():
            self._bg(self._airtable_upsert, chat_id, data, id_field)

    def _airtable_upsert(self, chat_id: str, data: Dict[str, Any], id_field: str):
        try:
            table = get_table(self.airtable_name)
            formula = f"{{{self._airtable_id_field()}}}={chat_id}" if str(chat_id).isdigit() else f"{{{self._airtable_id_field()}}}='{chat_id}'"
            records = table.all(formula=formula)
            at_data = self._map_to_airtable({**data, id_field: chat_id})
            if records:
                table.update(records[0]["id"], at_data)
            else:
                table.create(at_data)
        except Exception:
            pass

    def bulk_upsert(self, chat_id: str, data_list: List[Dict[str, Any]], id_field: str = "chat_id"):
        if not data_list: return
        
        # 1. Supabase Bulk Write
        if is_supabase_configured():
            payloads = [self._map_to_supabase({**d, "chat_id": str(chat_id)}) for d in data_list]
            self._bg(insert_rows, self.table_name, payloads, upsert=True, on_conflict=id_field)
            
        # 2. Airtable Bulk Write
        if is_airtable_available():
            self._bg(self._airtable_bulk_upsert, chat_id, data_list, id_field)

    def _airtable_bulk_upsert(self, chat_id: str, data_list: List[Dict[str, Any]], id_field: str):
        try:
            table = get_table(self.airtable_name)
            at_payloads = [self._map_to_airtable({**d, "chat_id": chat_id}) for d in data_list]
            for i in range(0, len(at_payloads), 10):
                table.batch_create(at_payloads[i:i+10])
        except Exception:
            pass

    def _airtable_id_field(self) -> str:
        return "Chat ID" if self.airtable_name != "Trailer Cache" else "Movie ID"
