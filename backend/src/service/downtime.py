from config.clients import redis_client
from models.schema import RazorpayWebhook

def process_downtime_event(payload: dict) -> dict:
    """
    Handles payment.downtime.started and payment.downtime.resolved events.
    """
    event = payload.get("event", "")
    
    if event == "payment.downtime.started":
        try:
            webhook = RazorpayWebhook.model_validate(payload)
            downtime = webhook.payload.payment_downtime.entity
        except Exception as e:
            print(f"[WEBHOOK ERROR] Downtime validation failed: {e}")
            return {"status": "validation failed"}
            
        method = downtime.method
        if method:
            redis_client.sadd("downtimes:method", method)
            if downtime.instrument:
                bank = downtime.instrument.bank or downtime.instrument.issuer
                if bank:
                    redis_client.setex(f"downtimes:{method}:{bank}", 3600, "1")
        return {"status": "downtime registered"}

    elif event == "payment.downtime.resolved":
        try:
            webhook = RazorpayWebhook.model_validate(payload)
            downtime = webhook.payload.payment_downtime.entity
        except Exception as e:
            print(f"[WEBHOOK ERROR] Downtime validation failed: {e}")
            return {"status": "validation failed"}
            
        method = downtime.method
        if method:
            redis_client.srem("downtimes:method", method)
        return {"status": "downtime cleared"}
        
    elif event.startswith("payment.downtime"):
        return {"status": "downtime event handled"}
        
    return {"status": "ignored"}

def detect_downtime(downtime):
    """
    Updates Redis with the latest downtime info.
    We store the down methods in a set, and specific instruments as keys.
    """
    method_key = "downtimes:method"
    
    instrument_dict = downtime.instrument.model_dump(exclude_none=True)
    
    if downtime.status == "resolved":
        redis_client.srem(method_key, downtime.method)
        for key, value in instrument_dict.items():
            instrument_key = f"downtimes:{downtime.method}:{value}"
            redis_client.delete(instrument_key)
        print(f"[DOWNTIME] Resolved for {downtime.method} - {instrument_dict}")
    else:
        redis_client.sadd(method_key, downtime.method)
        for key, value in instrument_dict.items():
            instrument_key = f"downtimes:{downtime.method}:{value}"
            redis_client.set(instrument_key, "down")
        print(f"[DOWNTIME] Active for {downtime.method} - {instrument_dict}")
