import calendar
from datetime import date, datetime

import razorpay
from config import Settings
from langchain_core.tools import tool
from models import RecoveryState

settings = Settings()
client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


@tool
def create_payment_link(state: RecoveryState):
    client.payment_link.create(
        {
            "amount": state.amount,
            "currency": state.currency,
            "customer": state.customer,
            "description": "Pending Payment. Please Update the Card",
            "expire_by": datetime.now() + datetime.hour(24),
        }
    )


@tool
def send_email_remainder():

    pass


@tool
def esclate_to_human():
    pass


@tool
def log_audit_entry():

    pass


@tool
def get_next_salary_date(target_date, reference_date=None):
    """
    Checks if a target_date is past the 1st, 15th, 30th,
    and all Fridays of the month of the reference_date (defaults to today).
    """

    if reference_date is None:
        reference_date = date.today()

    year = reference_date.year
    month = reference_date.month

    # 1. Define the fixed milestones (1st, 15th)
    milestones = [date(year, month, 1), date(year, month, 15)]
    try:
        milestones["30th"] = date(year, month, 30)
    except ValueError:
        milestones["30th"] = None

    # 2. Find all Fridays in the current calendar month
    month_cal = calendar.monthcalendar(year, month)
    fridays = [
        date(year, month, week[calendar.FRIDAY])
        for week in month_cal
        if week[calendar.FRIDAY] != 0
    ]

    results = []

    for dat in milestones + fridays:
        if dat > target_date:
            results.append(dat)

    return results


tools = [
    get_next_salary_date,
    log_audit_entry,
    send_email_remainder,
    esclate_to_human,
    create_payment_link,
]


# from datetime import datetime

# def send_email():
#     pass

# def escalte_human():
#     pass


# def handle_invoice(initial_date,last_updated,channel,response):
#     diff = last_updated+datetime.today()-initial_date
#     if diff < 15:
#         print(f"send email")
#         send_email()
#         channel = 'email'
#         last_updated = datetime.today()
#     if diff <  29:
#         print("Follow up email add urgency maik")
#         send_email()
#     if diff < 44:
#         print("Escalte to human")
#         escalte_human()
#     else:
#         print(f"send legal notcies")
#         escalte_human()


# def handle_checkout(intital_date,last_updated,channel,response,issue,attempts):
#     if attempts >= 3:
#         return

#     if issue == "payement_method_selection":
#         print("Send remainder")
#     else:
#         print("Update card enntry")

#     tdiff = intital_date.timedelta(datetime.now())
#     if tdiff <= 30:
#         print(f"First urgency")
#     elif tdiff <= 4:
#         print(f"Second nudge")
#     else:
#         print(f"Thrid nudeg")

#     return attempts+1,datetime.now(),"Email"


# async def handle_failed_payment(is_hard,last_updated,email):
#     if is_hard:
#         await handle_hard_declines()
#     tdiff = last_updated.timedelta(datetime.now()).hours
#     if tdiff < 24:
#         print("send remainder")
#     elif tdiff <  48:
#         print("esaclte")


# def handle_retry():

#     pass
# async def handle_failed_payment(is_hard,last_updated,attempts):
#     if is_hard:
#         await handle_hard_declines()
#     tdiff = last_updated.timedelta(datetime.now()).hours
#     nextsalary = check_milestones()
#     handle_retry(nextsalary)
#     if tdiff < 14 and attempts < 3:
#         print(f"send email")
#     if attempts > 3:
#         print(f"cancel+ winback")


# # import json

# with open('backend/data/sample_cases.json','r') as f:
#     data = json.loads(f)

# failed_txn = []
# failed_subs = []
# abandment = []
# overdue = []


# for point in data:
#     if point["type"].startswith("failed"):
#         failed_txn.append(Transaction(**point))
#     elif point["type"].startswith("abandment"):
#         abandment.append(Transaction(**point))
#     elif point["type"].startswith("overdue"):
#         overdue.append(Transaction(**point))
#     elif point["type"].startswith("failed_subrc"):
#         failed_subs.append(Transaction(**point))


# map(handle_failed_subscription,failed_txn)
# map(handle_checkout,abandment)
# map(handle_retry,failed_txn)


# def handle_checkout():
#     pass

# def handle_b2b_chaser():
#     pass


# async def handle_failed_subscription():
#     if transaction.status in hard_declines.values():
#         await handle_hard_declines(transaction)
#     milestones = check_milestones(datetime.today())
#     if transaction.failure_reason == "Insufficent funds":
#         if transaction.attemps == 0:
#             print(f"celery job to ffire on 15th day sales link")
#         elif transaction.attemps == 1:
#             print(f"print email")
#         else:
#             print(f"10% discount ")


# def handle_drop_off():
#     pass


# from datetime import datetime


# # def handle_retry(transaction:Transaction):
# #     if transaction.failure_reason in hard_declines.values():
# #         handle_hard_declines(transaction)
# #     date = datetime.datetime()

# #     pass

# async def handle_overdue(state:RecoveryState):
#     if 7 <= overdue <= 14:
#         print("Send an email")
#     elif 15 <= overdue <= 29:
#         print("Followup send urgency ")
#     elif 30 <= overdue <= 44:
#         print(f"handle senior contack")
#     else:
#         print("Sendd legal noices")
