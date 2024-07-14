from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseRedirect
from .shopify_utils import *
from django.core.mail import send_mail
from django.urls import reverse

def user_login(request):
    error_message = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('catalog')
        else:
            error_message = 'Invalid login details'
    return render(request, 'catalog/login.html', {'error_message': error_message})

def user_logout(request):
    logout(request)
    return redirect('login')

@login_required
def index(request):
    search_query = request.GET.get('search', '').strip().lower()
    after = request.GET.get('after', None)
    before = request.GET.get('before', None)

    products, page_info = fetch_products_from_graphql(search_query, after, before)

    # Apply pricing rules to all products
    products = apply_pricing_rules(request.user, products)
    for product in products:
        product['original_price_per_measurement'] = (product['original_price'] / product['measurement_value']).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if product.get('special_price') is not None:
            product['special_price_per_measurement'] = (product['special_price'] / product['measurement_value']).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    context = {
        'products': products,
        'next_page_info': page_info['endCursor'] if page_info['hasNextPage'] else None,
        'prev_page_info': page_info['startCursor'] if page_info['hasPreviousPage'] else None,
        'search_query': search_query,  # Pass search query to context
    }
    return render(request, 'catalog/catalog.html', context)

@login_required
def check_stock(request, product_id):
    stock_level, unit = check_stock_level(product_id)
    return JsonResponse({'stock': stock_level, 'unit': unit})

@login_required
def submit_order(request, product_id):
    if request.method == 'POST':
        quantity = request.POST.get('quantity')
        product_title = request.POST.get('product_title')

        print(f"Received order for product ID: {product_id}, Title: {product_title}, Quantity: {quantity}")

        subject = f'Order for {product_title}'
        message = f'Product ID: {product_id}\nProduct Title: {product_title}\nQuantity: {quantity}\nUser: {request.user.username}\nthis is a test, please ignore. thank you.'
        recipient_list = [settings.ORDER_EMAIL_RECIPIENT]

        print(f"Sending email to {recipient_list} with subject '{subject}'")

        try:
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list)
            print("Email sent successfully")
        except Exception as e:
            print(f"Error sending email: {e}")

        return HttpResponseRedirect(reverse('catalog'))
    return render(request, 'catalog/catalog.html')