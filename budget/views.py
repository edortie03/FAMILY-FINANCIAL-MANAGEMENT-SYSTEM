from django.shortcuts import render, redirect, HttpResponse
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Transaction, Expense
from .forms import TransactionForm
from django.db.models import Sum
import csv


def export_transactions_to_csv(request):
    user = request.user
    transactions = Transaction.objects.filter(user=user)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="transactions_{user.username}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow(["Date", "Category", "Amount", "Type"])

    for tx in transactions:
        writer.writerow([tx.date, tx.category, tx.amount, tx.type])

    return response


def home(request):
    return render(request, "budget/home.html")


def about(request):
    return render(request, "budget/about_us.html")


def register(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        # Basic validations
        if not username or not email or not password or not confirm_password:
            messages.error(request, "All fields are required.")
            return redirect("register")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email is already registered.")
            return redirect("register")

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect("register")

        if len(password) > 10:
            messages.error(request, "Password should not exceed 8 digits.")
            return redirect("register")

        # Create the user
        try:
            User.objects.create_user(
                username=username,
                email=email,
                password=password,
            )
            messages.success(request, "Registration successful! Please log in.")
            return redirect("login")
        except Exception as e:
            messages.error(request, f"An error occurred: {e}")
            return redirect("register")
    else:
        return render(request, "budget/register.html")


def login(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]

        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.is_active:
                auth_login(request, user)
                # Redirect to the dashboard after login
                return redirect("dashboard")
            else:
                messages.error(request, "Your account is disabled.")
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "budget/login.html")


def dashboard(request):
    user = request.user
    transactions = Transaction.objects.filter(user=user).order_by("-date")[:10]

    total_balance = sum(
        [t.amount if t.type == "income" else -t.amount for t in transactions]
    )
    total_income = sum([t.amount for t in transactions if t.type == "income"])
    total_expenses = sum(
        [t.amount for t in transactions if t.type == "expense"]
    )

    recommendation = ""
    if total_income == 0:
        recommendation = (
            "You have no income. Please add some income to manage your budget."
        )
    elif total_balance > 10000:
        recommendation = (
            "You are in a good financial position. Consider saving or "
            "investing your surplus."
        )

    elif total_balance <= 10000:
        recommendation = (
            "please consider rechecking your expenses,"
            " you are running out of balance."
        )
    else:
        recommendation = "You're breaking even. Monitor your spending to save more."

    context = {
        "total_balance": total_balance,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "transactions": transactions,
        "recommendation": recommendation,
    }

    return render(request, "budget/dashboard.html", context)


def add_income(request):
    if request.method == "POST":
        form = TransactionForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.user = request.user
            transaction.type = "income"
            transaction.save()
            return redirect("dashboard")
    else:
        form = TransactionForm()

    return render(request, "budget/add_income.html", {"form": form})


def add_expense(request):
    if request.method == "POST":
        category = request.POST.get("category")

        try:
            expense_amount = float(request.POST.get("amount"))
        except (ValueError, TypeError):
            messages.error(request, "Invalid amount.")
            return redirect(
                "add_expense"
            )  # Redirect to the same page if the amount is invalid

        # Calculate the total balance of the user (Income - Expenses)
        total_income = (
            Transaction.objects.filter(user=request.user, type="income").aggregate(
                Sum("amount")
            )["amount__sum"]
            or 0
        )
        total_expenses = (
            Transaction.objects.filter(user=request.user, type="expense").aggregate(
                Sum("amount")
            )["amount__sum"]
            or 0
        )
        balance = total_income - total_expenses

        # Check if the user has enough balance to add this expense
        if expense_amount > balance:
            messages.error(
                request, "You do not have enough balance to add this expense."
            )
            return redirect("add_expense")  # Redirect to the same page

        # Create and save the expense
        expense = Expense.objects.create(
            user=request.user,
            amount=expense_amount,
            category=category,
            date=request.POST.get(
                "date"
            ),  # Use the provided date, or you can add validation for it
        )
        expense.save()

        # Save the transaction for expense in the Transaction model
        transaction = Transaction(
            user=request.user,
            amount=expense_amount,
            date=request.POST.get("date"),
            category=category,
            type="expense",  # Set the type to 'expense'
        )
        transaction.save()

        # Show success message and redirect to the dashboard or another page
        messages.success(request, "Expense added successfully.")
        return redirect(
            "dashboard"
        )  # Redirect to the dashboard after saving the expense

    return render(request, "budget/add_expense.html")


@login_required
def history(request):
    transactions = Transaction.objects.filter(user=request.user).order_by(
        "-date"
    )  # Sort by most recent
    context = {"transactions": transactions}
    return render(request, "budget/history.html", context)


@login_required
def logout_view(request):
    logout(request)
    return redirect("/")
