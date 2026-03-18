import random
import re
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod
from flask import Flask, request, render_template

app = Flask(__name__)

# --- FUNCIONES DE VALIDACIÓN ---

def validar_luhn(card_number: str) -> bool:
    """Valida un número de tarjeta usando el algoritmo de Luhn."""
    card_number = card_number.replace(" ", "").replace("-", "")
    if not card_number.isdigit() or len(card_number) < 13:
        return False
    
    digitos = [int(x) for x in str(card_number)]
    impares = digitos[-1::-2]
    pares = [sum(divmod(2 * d, 10)) for d in digitos[-2::-2]]
    return (sum(impares) + sum(pares)) % 10 == 0

# --- MODELOS Y ESTRATEGIAS DE PAGO ---

@dataclass
class PaymentResult:
    success: bool
    transaction_id: str
    message: str

class PaymentStrategy(ABC):
    @abstractmethod
    def process_payment(self, amount: float) -> PaymentResult:
        pass

class CreditCardStrategy(PaymentStrategy):
    def __init__(self, card_number: str, cvv: str, expiry_date: str):
        self.card_number = card_number.replace(" ", "")
        self.cvv = cvv
        self.expiry_date = expiry_date

    def process_payment(self, amount: float) -> PaymentResult:
        if not validar_luhn(self.card_number):
            return PaymentResult(False, "", "El número de tarjeta es inválido.")
            
        if not self.cvv.isdigit() or len(self.cvv) not in [3, 4]:
            return PaymentResult(False, "", "CVV inválido.")

        try:
            exp_date = datetime.strptime(self.expiry_date, "%m/%y")
            hoy = datetime.now()
            if exp_date.year < hoy.year or (exp_date.year == hoy.year and exp_date.month < hoy.month):
                return PaymentResult(False, "", "La tarjeta está vencida.")
        except ValueError:
            return PaymentResult(False, "", "Formato de fecha inválido. Usa MM/YY.")

        tarjeta_oculta = f"**** **** **** {self.card_number[-4:]}"
        
        if random.random() < 0.85:
            txn_id = f"TXN-CC-{random.randint(100000, 999999)}"
            return PaymentResult(True, txn_id, f"Cobro exitoso de ${amount} a la tarjeta {tarjeta_oculta}.")
        return PaymentResult(False, "", "Pago declinado por el banco (fondos insuficientes).")

class PayPalStrategy(PaymentStrategy):
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password

    def process_payment(self, amount: float) -> PaymentResult:
        email_regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        if not re.match(email_regex, self.email):
            return PaymentResult(False, "", "El formato del correo de PayPal es inválido.")
        
        if len(self.password) < 6:
            return PaymentResult(False, "", "Credenciales inválidas. La contraseña debe tener al menos 6 caracteres.")
        
        if random.random() < 0.85:
            txn_id = f"PAYID-{random.randint(10000000, 99999999)}"
            return PaymentResult(True, txn_id, f"Autenticación exitosa. Cobro procesado en la cuenta {self.email}.")
        return PaymentResult(False, "", "Autenticación fallida o cuenta de PayPal sin fondos.")

class BankTransferStrategy(PaymentStrategy):
    def __init__(self, bank_name: str, account_number: str, account_holder: str, swift_code: str):
        self.bank_name = bank_name
        self.account_number = account_number
        self.account_holder = account_holder
        self.swift_code = swift_code.replace(" ", "").upper()

    def process_payment(self, amount: float) -> PaymentResult:
        if len(self.account_holder) < 3:
            return PaymentResult(False, "", "Nombre del titular inválido.")
            
        if not self.account_number.isdigit() or len(self.account_number) < 8:
            return PaymentResult(False, "", "Número de cuenta inválido (debe tener al menos 8 dígitos).")

        swift_regex = r'^[A-Z0-9]{8,11}$'
        if not re.match(swift_regex, self.swift_code):
            return PaymentResult(False, "", "Código SWIFT/BIC inválido. Debe contener entre 8 y 11 caracteres.")
        
        if random.random() < 0.90:
            txn_id = f"TRN-{random.randint(100000, 999999)}"
            return PaymentResult(True, txn_id, f"Transferencia enviada a {self.bank_name} a nombre de {self.account_holder}.")
        return PaymentResult(False, "", "La red interbancaria rechazó la transacción por inconsistencia de datos.")

class CheckoutContext:
    def __init__(self):
        self._strategy: Optional[PaymentStrategy] = None

    def set_strategy(self, strategy: PaymentStrategy):
        self._strategy = strategy

    def execute_checkout(self, amount: float) -> PaymentResult:
        if not self._strategy:
            return PaymentResult(False, "", "Error interno: No se ha seleccionado un método de pago.")
        return self._strategy.process_payment(amount)

# --- BASE DE DATOS SIMULADA ---

PRODUCTS = {
    "1": {"name": "Teclado Mecánico RGB", "price": 120.50, "image": "⌨️"},
    "2": {"name": "Ratón Inalámbrico", "price": 45.00, "image": "🖱️"},
    "3": {"name": "Monitor 24 pulgadas", "price": 199.99, "image": "🖥️"}
}

# --- RUTAS DE FLASK ---

@app.route("/")
def index():
    return render_template("index.html", products=PRODUCTS)

@app.route("/checkout/<product_id>")
def checkout(product_id):
    product = PRODUCTS.get(product_id)
    if not product:
        return "Producto no encontrado", 404
    return render_template("checkout.html", product=product, product_id=product_id)

@app.route("/process_payment", methods=["POST"])
def process_payment():
    amount = float(request.form.get("amount", 0))
    method = request.form.get("payment_method")
    
    context = CheckoutContext()
    
    if method == "credit_card":
        card_number = request.form.get("card_number", "")
        cvv = request.form.get("cvv", "")
        expiry_date = request.form.get("expiry_date", "")
        context.set_strategy(CreditCardStrategy(card_number, cvv, expiry_date))
        
    elif method == "paypal":
        email = request.form.get("paypal_email", "")
        password = request.form.get("paypal_password", "")
        context.set_strategy(PayPalStrategy(email, password))
        
    elif method == "bank_transfer":
        bank_name = request.form.get("bank_name", "")
        account_number = request.form.get("account_number", "")
        account_holder = request.form.get("account_holder", "")
        swift_code = request.form.get("swift_code", "")
        context.set_strategy(BankTransferStrategy(bank_name, account_number, account_holder, swift_code))
        
    result = context.execute_checkout(amount)
    return render_template("result.html", result=result)

if __name__ == "__main__":
    app.run(debug=True)