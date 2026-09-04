from config.clients import get_redis_client
from config.logger import get_logger
from models.schema import RazorpayWebhook

logger = get_logger(__name__)

async def process_downtime_event(payload: dict) -> dict:
    """
    Handles payment.downtime.started and payment.downtime.resolved events.
    """
    event = payload.get("event", "")
    redis = get_redis_client()
    
    if event == "payment.downtime.started":
        try:
            webhook = RazorpayWebhook.model_validate(payload)
            downtime = webhook.payload.payment_downtime.entity
        except Exception as e:
            logger.error(f"[WEBHOOK ERROR] Downtime validation failed: {e}")
            return {"status": "validation failed"}
            
        method = downtime.method
        if method:
            await redis.sadd("downtimes:method", method)
            if downtime.instrument:
                bank = downtime.instrument.bank or downtime.instrument.issuer
                if bank:
                    await redis.setex(f"downtimes:{method}:{bank}", 3600, "1")
                    await redis.setex(f"downtimes:{method}:{bank.upper()}", 3600, "1")
            else:
                await redis.setex(f"downtimes:{method}:all", 3600, "1")
        return {"status": "downtime registered"}

    elif event == "payment.downtime.resolved":
        try:
            webhook = RazorpayWebhook.model_validate(payload)
            downtime = webhook.payload.payment_downtime.entity
        except Exception as e:
            logger.error(f"[WEBHOOK ERROR] Downtime validation failed: {e}")
            return {"status": "validation failed"}
            
        method = downtime.method
        if method:
            if downtime.instrument:
                bank = downtime.instrument.bank or downtime.instrument.issuer
                if bank:
                    await redis.delete(f"downtimes:{method}:{bank}")
                    await redis.delete(f"downtimes:{method}:{bank.upper()}")
            else:
                await redis.delete(f"downtimes:{method}:all")

            # Only remove method if no specific instruments or 'all' flags remain down
            remaining = await redis.keys(f"downtimes:{method}:*")
            if not remaining:
                await redis.srem("downtimes:method", method)
        return {"status": "downtime cleared"}
        
    elif event.startswith("payment.downtime"):
        return {"status": "downtime event handled"}
        
    return {"status": "ignored"}

async def detect_downtime(downtime):
    """
    Updates Redis with the latest downtime info.
    We store the down methods in a set, and specific instruments as keys.
    """
    redis = get_redis_client()
    method_key = "downtimes:method"
    
    instrument_dict = downtime.instrument.model_dump(exclude_none=True) if downtime.instrument else {}
    
    if downtime.status == "resolved":
        for key, value in instrument_dict.items():
            instrument_key = f"downtimes:{downtime.method}:{value}"
            await redis.delete(instrument_key)
            await redis.delete(f"{instrument_key.upper()}")
        remaining = await redis.keys(f"downtimes:{downtime.method}:*")
        if not remaining:
            await redis.srem(method_key, downtime.method)
        logger.info(f"[DOWNTIME] Resolved for {downtime.method} - {instrument_dict}")
    else:
        await redis.sadd(method_key, downtime.method)
        for key, value in instrument_dict.items():
            instrument_key = f"downtimes:{downtime.method}:{value}"
            await redis.set(instrument_key, "down")
            await redis.set(f"{instrument_key.upper()}", "down")
        logger.info(f"[DOWNTIME] Active for {downtime.method} - {instrument_dict}")
