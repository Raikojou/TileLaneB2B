import shopify
import requests
import re
from django.conf import settings
from .models import PricingRule
from decimal import Decimal, ROUND_HALF_UP

# little utility regex to extract numbers from graphQL id because WHY THE FUCK CANT SHOPIFY BE CONSISTENT FFS
def extract_numeric_id(gid):
    return re.search(r'\d+$', gid).group()

# a stripper for trailing zeroes. ha.
def format_discount(price):
    return '{:.2f}'.format(price).rstrip('0').rstrip('.')

def shopify_graphql(query):
    url = f"https://{settings.SHOPIFY_SHOP_NAME}.myshopify.com/api/2024-07/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Storefront-Access-Token": settings.SHOPIFY_API_PASSWORD
    }
    response = requests.post(url, json={'query': query}, headers=headers)
    response.raise_for_status()
    return response.json()

'''
Admin API (what we used to use) supports query filter SKU, but storefront API doesnt.
But Storefront API has unit info, which admin API doesn't.
Blame this fucking issue with Shopify.
'''
def fetch_products_from_graphql(search_query=None, after=None, before=None):
    query_filter = f'(title:{search_query}*)' if search_query else ''
    pagination_args = ''
    if after:
        pagination_args = f'after: "{after}", first: 50'
    elif before:
        pagination_args = f'before: "{before}", last: 50'
    else:
        pagination_args = 'first: 50'
    query = f"""
    {{
        products({pagination_args}, query: "(status:active) AND {query_filter}", sortKey: TITLE) {{
            edges {{
                node {{
                    id
                    title
                    images(first: 10) {{
                        edges {{
                            node {{
                                url
                            }}
                        }}
                    }}
                    variants(first: 1) {{
                        edges {{
                            node {{
                                price {{
                                    amount
                                }}
                                unitPriceMeasurement {{
                                    quantityValue
                                    quantityUnit
                                }}
                            }}
                        }}
                    }}
                    collections(first: 15) {{
                        edges {{
                            node {{
                                id
                            }}
                        }}
                    }}
                }}
            }}
            pageInfo {{
                hasNextPage
                hasPreviousPage
                startCursor
                endCursor
            }}
        }}
    }}
    """
    result = shopify_graphql(query)

    products = result['data']['products']['edges']
    page_info = result['data']['products']['pageInfo']
    
    product_list = []
    for product in products:
        node = product['node']
        product_data = {
            'id': extract_numeric_id(node['id']),
            'title': node['title'],
            'images': [image['node']['url'] for image in node['images']['edges']],
            'collections': [extract_numeric_id(collection['node']['id']) for collection in node['collections']['edges']],
            'original_price': Decimal(node['variants']['edges'][0]['node']['price']['amount']).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'measurement_value': Decimal(node['variants']['edges'][0]['node']['unitPriceMeasurement']['quantityValue']),
            'measurement_unit': node['variants']['edges'][0]['node']['unitPriceMeasurement']['quantityUnit']
        }
        product_list.append(product_data)
    
    return product_list, page_info

# Priority list:
# 1st = individual product special price, 2nd = individual product special discount
# 3rd = collection special price, 4th = collection special discount
# 5th = user-level base discount (default is 0 set in accounts.Model)
def apply_pricing_rules(user, products):
    base_discount_factor = Decimal(1 - user.userprofile.base_discount / 100)

    for product in products:
        product_id = str(product['id'])
        collection_ids = [collection for collection in product['collections']]
        applied_discount = False                        # switched TRUE if discounted on product level, else pass to check collection, else pass to check user=level base discount
        
        product_rules = PricingRule.objects.filter(user=user)
        for rule in product_rules:
            if rule.product_ids and product_id in rule.product_ids.split(','):
                if rule.special_price:
                    product['special_price'] = Decimal(rule.special_price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    applied_discount = True
                    break
                elif rule.discount_percentage:
                    discount_factor = Decimal(1 - rule.discount_percentage / 100)
                    product['discount_factor'] = format_discount(rule.discount_percentage)            # this and subsequent special discounts will pass discount_factor. dunno if this is important or not.
                    product['special_price'] = (product['original_price'] * discount_factor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    applied_discount = True
                    break

        if not applied_discount:
            for rule in product_rules:
                if rule.collection_ids:
                    rule_collection_ids = rule.collection_ids.split(',')
                    if any(collection_id in rule_collection_ids for collection_id in collection_ids):
                        if rule.special_price:
                            product['special_price'] = Decimal(rule.special_price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                            applied_discount = True
                            break
                        elif rule.discount_percentage:
                            discount_factor = Decimal(1 - rule.discount_percentage / 100)
                            product['discount_factor'] = format_discount(rule.discount_percentage)
                            product['special_price'] = (product['original_price'] * discount_factor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                            applied_discount = True
                            break

        if not applied_discount and base_discount_factor != 1:
            product['discount_factor'] = format_discount(user.userprofile.base_discount)
            product['special_price'] = (product['original_price'] * base_discount_factor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    return products

'''
Reason for separate func to check stock level is twofold:
1. Reduce load on initial API call, to prevent IP from getting softblocked by shopify server
2. Spit out stock only when requested to make sure quantity is always up to date to the second of request
'''
def check_stock_level(product_id):
    query = f"""
    {{
        product(id: "gid://shopify/Product/{product_id}") {{
            variants(first: 1) {{
                edges {{
                    node {{
                        quantityAvailable
                    }}
                }}
            }}
            metafield(key: "unit", namespace: "productDetails") {{
                value
            }}
        }}
    }}
    """
    result = shopify_graphql(query)
    stock_level = result['data']['product']['variants']['edges'][0]['node']['quantityAvailable']
    unit = result['data']['product']['metafield']['value']
    return stock_level, unit