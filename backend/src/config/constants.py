


hard_declines = {
        "03": "Invalid merchant",
        "04": "Pick up card (No fraud)",
        "07": "Pick up card (fraud)",
        "12": "Invalid transaction",
        "13": "Invalid amount",
        "14": "Invalid account/ card number",
        "15": "No such issuer",
        "25": "Unable to locate record in file",
        "41": "Lost card, pick up",
        "43": "Stolen card, pick up",
        "52": "No checking account",
        "53": "No savings account",
        "54": "Expired card",
        "57": "Transaction not permitted - card",
        "58": "Transaction not permitted - terminal",
        "59": "Suspected fraud",
        "62": "Invalid/restricted service code",
        "63": "Security violation",
        "64": "Transaction does not fulfill AML requirement",
        "75": "Allowable number of PIN entry tries exceeded",
        "79": "Already reversed",
        "93": "Transaction can't be completed - violation of law",
        "R0": "Recurring charge stopped at customer request",
        "R1": "Recurring charge stopped at customer request"
    }
    
    
soft_declines  =  {
        "01": "Refer to issuer",
        "02": "Refer to issuer (special condition)",
        "05": "Do not honor",
        "06": "Error",
        "10": "Partial approval",
        "19": "Re-enter transaction",
        "21": "No action taken",
        "28": "File temporarily not available for update or injury",
        "51": "Insufficient funds",
        "55": "Incorrect PIN",
        "61": "Exceeds approval amount limit",
        "65": "Exceeds withdrawal limit/ activity limit",
        "70": "PIN data required",
        "76": "Unsolicited reversal",
        "78": "Blocked, first use",
        "82": "Negative CAM, dCVV, iCVV, or CVV results",
        "85": "No reason to decline",
        "86": "Cannot verify PIN",
        "91": "Issuer or switch unavailable",
        "92": "Unable to route transaction",
        "96": "System error",
        "97": "Invalid CVV",
        "1A": "Additional customer authentication required"
    }




email_messages = {
    'gentle': "Hi {name},<br><br>We noticed your recent payment of ₹{amount} failed. Please ensure your account has sufficient funds. We'll retry soon.<br><br>Thanks,<br>The Team",
    'urgent': "Hi {name},<br><br>Your payment of ₹{amount} has failed again. To avoid service interruption, please update your payment method immediately.<br><br>Thanks,<br>The Team",
    'final': "Dear {name},<br><br>This is our final notice regarding your outstanding payment of ₹{amount}. Your service will be paused if this is not resolved.<br><br>Thanks,<br>The Team"
}



STATUS_ORDER = {"escalated": 0, "in_progress": 1, "pending": 2, "recovered": 3, "closed": 4}


HANDLED_EVENTS = [
    "payment.failed", 
    "payment.captured",
    "payment.dispute.created",
    "payment_link.expired",
    "subscription.halted",
    "subscription.cancelled",
    "invoice.expired",
    "order.created"


]
