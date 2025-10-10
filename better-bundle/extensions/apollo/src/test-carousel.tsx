// Test file to verify ImageCarousel component works
import { ImageCarousel } from "./components/ImageCarousel";

// Sample test data
const sampleImages = [
  {
    url: "https://cdn.shopify.com/s/files/1/0000/0000/products/product1_1.jpg",
    alt_text: "Product image 1"
  },
  {
    url: "https://cdn.shopify.com/s/files/1/0000/0000/products/product1_2.jpg", 
    alt_text: "Product image 2"
  },
  {
    url: "https://cdn.shopify.com/s/files/1/0000/0000/products/product1_3.jpg",
    alt_text: "Product image 3"
  }
];

// Test component
export function TestCarousel() {
  return (
    <ImageCarousel 
      images={sampleImages}
      productTitle="Test Product"
    />
  );
}

// Test with single image
export function TestSingleImage() {
  return (
    <ImageCarousel 
      images={[sampleImages[0]]}
      productTitle="Single Image Product"
    />
  );
}

// Test with no images
export function TestNoImages() {
  return (
    <ImageCarousel 
      images={[]}
      productTitle="No Images Product"
    />
  );
}
