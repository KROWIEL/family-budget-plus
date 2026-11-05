from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str
    password: str


class ProfileIn(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=40)
    avatar: str | None = None
    theme: str | None = None
    report_currency: str | None = None


class PasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=4, max_length=100)


class AccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    kind: str = "card"          # income | card | cash | savings
    owner_id: int | None = None
    currency: str = "BYN"       # BYN | USD
    icon: str = "wallet"
    color: str = "#6366f1"
    goal_amount: float = Field(default=0, ge=0)   # цель по сумме (только копилка); 0 = без цели


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    description: str = ""
    icon: str = "shopping-cart"
    color: str = "#6366f1"
    monthly_limit: float | None = Field(default=0, ge=0)   # None/0 = без лимита
    limit_currency: str = "BYN"


class TransactionIn(BaseModel):
    type: str                    # income | expense | transfer | debt_payment
    amount: float = Field(gt=0)
    account_id: int
    dest_account_id: int | None = None
    category_id: int | None = None
    debt_id: int | None = None
    note: str = ""
    occurred_at: str | None = None   # YYYY-MM-DD
    # Если задано при переводе или платеже в другой валюте — это сумма на стороне
    # получателя (счёт или долг), а amount остаётся фактическим списанием с карты:
    # банк может сконвертировать не по курсу НБРБ.
    applied_amount: float | None = None


class DebtIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    kind: str = "credit"          # debt | credit | leasing
    creditor: str = ""
    currency: str = "BYN"         # BYN | USD
    total_amount: float = Field(ge=0)
    remaining_start: float = Field(ge=0)
    monthly_payment: float = Field(default=0, ge=0)
    pay_day: int = Field(default=0, ge=0, le=31)
    icon: str = "landmark"
    color: str = "#f43f5e"
    note: str = ""
