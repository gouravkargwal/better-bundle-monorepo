# Mercury Checkout UI Extension

Mercury is a **Checkout UI Extension** for Shopify that displays personalized product recommendations during the checkout process. It integrates with the BetterBundle recommendation engine to show "last chance to add" suggestions that can increase average order value.

## 🎯 Features

- **Personalized Recommendations**: Shows relevant products based on cart contents
- **Attribution Tracking**: Tracks which recommendations lead to purchases for billing
- **Responsive Design**: Works seamlessly on desktop and mobile checkout
- **Configurable Settings**: Merchants can customize title, limit, and backend URL
- **Error Handling**: Graceful fallbacks when recommendations fail to load
- **Analytics Integration**: Tracks recommendation interactions for performance analysis

## 🏗️ Architecture

### Components

- **Extension**: Main component that orchestrates the recommendation flow
- **RecommendationCard**: Individual product recommendation display
- **LoadingSpinner**: Loading state indicator

### Data Flow

1. **Load Recommendations**: Fetches recommendations from Python worker API
2. **Display Products**: Shows recommendation cards with product details
3. **Add to Cart**: Adds recommended products to cart with attribution
4. **Track Interactions**: Sends analytics data to backend

## ⚙️ Configuration

### Settings (shopify.extension.toml)

```toml
[extensions.settings]
[[extensions.settings.fields]]
key = "recommendation_title"
type = "single_line_text_field"
name = "Recommendation Title"
default = "Last chance to add"

[[extensions.settings.fields]]
key = "recommendation_limit"
type = "number_integer_field"
name = "Number of Recommendations"
default = 3

[[extensions.settings.fields]]
key = "backend_url"
type = "single_line_text_field"
name = "Backend URL"
description = "Your BetterBundle backend URL"
```

### API Integration

The extension calls your Python worker API at:

```
POST {backend_url}/api/v1/recommendations/
```

**Request Body:**

```json
{
  "shop_domain": "shop.myshopify.com",
  "context": "checkout",
  "product_id": "123456789",
  "user_id": null,
  "session_id": null,
  "limit": 3
}
```

**Response:**

```json
{
  "success": true,
  "recommendations": [
    {
      "id": "987654321",
      "title": "Recommended Product",
      "handle": "recommended-product",
      "image": "https://...",
      "price": "29.99",
      "currency": "USD",
      "variantId": "987654321",
      "reason": "Frequently bought together"
    }
  ]
}
```

## 🎨 UI Components

### RecommendationCard

- **Product Image**: Shows product image with fallback
- **Product Title**: Displays product name
- **Price**: Shows formatted price with currency
- **Reason**: Optional recommendation reason
- **Add to Cart Button**: Adds product to cart with attribution

### Styling

- Uses Shopify's native UI components for consistency
- Responsive layout that works on all devices
- Follows Shopify's design guidelines

## 📊 Attribution System

### How It Works

1. **Generate Attribution ID**: Creates unique ID for each recommendation interaction
2. **Store in Cart Attributes**: Saves attribution data in cart attributes
3. **Track Interactions**: Sends analytics events to backend
4. **Order Processing**: Backend processes attributions during daily order sync

### Attribution Data Structure

```json
{
  "id": "ui_attr_1234567890_abc123",
  "extension_type": "checkout",
  "product_id": "987654321",
  "timestamp": 1234567890,
  "source": "mercury_extension"
}
```

## 🚀 Installation & Setup

### Prerequisites

- Shopify Plus store (required for checkout UI extensions)
- BetterBundle app installed
- Python worker backend running

### Installation Steps

1. **Install the App**: Install BetterBundle app from Shopify App Store
2. **Configure Backend**: Set your Python worker URL in extension settings
3. **Customize Settings**: Adjust recommendation title and limit
4. **Enable Extension**: Add Mercury to your checkout in Shopify admin

### Shopify Admin Setup

1. Go to **Settings** → **Checkout**
2. Click **Customize checkout**
3. Click **Add app** → Select "Mercury"
4. Position the extension in your checkout flow
5. Save changes

## 🧪 Testing

### Development Testing

```bash
# Start development server
shopify app dev

# Test in checkout preview
# Use the provided preview URL to test the extension
```

### Production Testing

1. **Place Test Orders**: Add items to cart and go through checkout
2. **Verify Recommendations**: Check that recommendations appear
3. **Test Add to Cart**: Ensure recommended products can be added
4. **Check Attribution**: Verify attribution data is stored correctly

## 📈 Analytics & Performance

### Tracked Events

- **recommendation_displayed**: When recommendations are shown
- **recommendation_clicked**: When user clicks on recommendation
- **recommendation_add_to_cart**: When user adds recommended product

### Performance Metrics

- **Load Time**: How fast recommendations load
- **Conversion Rate**: Percentage of recommendations that lead to purchases
- **Revenue Impact**: Additional revenue generated by recommendations

## 🔧 Troubleshooting

### Common Issues

1. **Recommendations Not Loading**
   - Check backend URL configuration
   - Verify Python worker is running
   - Check browser console for errors

2. **Add to Cart Failing**
   - Ensure checkout allows cart modifications
   - Check product variant IDs are correct
   - Verify cart permissions

3. **Attribution Not Working**
   - Check cart attributes are being set
   - Verify backend processes order attributes
   - Ensure attribution IDs are unique

### Debug Mode

Enable debug logging by checking browser console for:

- API request/response logs
- Attribution data
- Error messages

## 🔄 Updates & Maintenance

### Regular Updates

- **API Compatibility**: Ensure compatibility with Python worker updates
- **Shopify Updates**: Keep extension compatible with Shopify platform changes
- **Performance Optimization**: Monitor and optimize loading times

### Monitoring

- **Error Rates**: Track API failures and cart update errors
- **Performance**: Monitor recommendation load times
- **Conversion**: Track recommendation-to-purchase conversion rates

## 📝 License

This extension is part of the BetterBundle app and follows the same licensing terms.

## 🤝 Support

For support and questions:

- Check the BetterBundle documentation
- Contact support through the app
- Review Shopify's checkout UI extension documentation
