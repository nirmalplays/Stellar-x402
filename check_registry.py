import os
import time
from api.services.registry_client import registry_client
from stellar_sdk import xdr
from dotenv import load_dotenv

load_dotenv()

def parse_scval(sc_val):
    if sc_val.type == xdr.SCValType.SCV_VOID:
        return None
    if sc_val.type == xdr.SCValType.SCV_I64:
        return sc_val.i64.int64
    if sc_val.type == xdr.SCValType.SCV_BOOL:
        return sc_val.b
    if sc_val.type == xdr.SCValType.SCV_STRING:
        return sc_val.str.sc_string.decode()
    if sc_val.type == xdr.SCValType.SCV_SYMBOL:
        return sc_val.sym.sc_symbol.decode()
    if sc_val.type == xdr.SCValType.SCV_MAP:
        res = {}
        if sc_val.map and sc_val.map.sc_map:
            for entry in sc_val.map.sc_map:
                key = parse_scval(entry.key)
                val = parse_scval(entry.val)
                res[key] = val
        return res
    if sc_val.type == xdr.SCValType.SCV_ADDRESS:
        # Simplification: return the account ID
        return str(sc_val.address)
    return f"Unsupported type: {sc_val.type}"

def check_agent(agent_id):
    print(f"Checking agent: {agent_id}...")
    try:
        agent_data = registry_client.get_agent(agent_id)
        if not agent_data:
            print(f"Agent {agent_id} NOT found in registry.")
            return

        sc_val = xdr.SCVal.from_xdr(agent_data)
        parsed = parse_scval(sc_val)
        
        if parsed is None:
            print(f"Agent {agent_id} NOT found in registry (returned Void).")
            return

        print(f"Agent {agent_id} Details:")
        if isinstance(parsed, dict):
            for k, v in parsed.items():
                print(f"  {k}: {v}")
        else:
            print(f"  Value: {parsed}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error checking {agent_id}: {e}")

if __name__ == "__main__":
    check_agent("agent_402")
