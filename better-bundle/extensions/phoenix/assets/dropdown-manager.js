/**
 * DropdownManager - Handles dropdown interactions, validation, and dependent dropdowns
 * Optimized for performance with minimal DOM queries and efficient event handling
 */
class DropdownManager {
  constructor() {
    this.isUpdatingDropdowns = false;
    this.variantManager = new VariantManager();
  }

  // Handle dropdown change with validation
  handleDropdownChange(productId, optionName, dropdownElement) {
    const selectedValue = dropdownElement.value;
    const selectedOption = dropdownElement.querySelector(`option[value="${selectedValue}"]`);

    // Check if the selected option is disabled or unavailable
    if (selectedOption && (selectedOption.disabled || selectedOption.classList.contains('unavailable'))) {
      // Store the previous valid value before reverting
      const productCard = document.querySelector(`[data-product-id="${productId}"]`);
      const currentSelections = this.getSelectedOptions(productCard);
      const previousValue = currentSelections[optionName];

      // Force revert immediately
      if (previousValue && !dropdownElement.querySelector(`option[value="${previousValue}"]`)?.disabled) {
        dropdownElement.value = previousValue;
      } else {
        // Find first available option
        const availableOptions = Array.from(dropdownElement.querySelectorAll('option:not([disabled]):not(.unavailable):not([value=""])'));
        if (availableOptions.length > 0) {
          dropdownElement.value = availableOptions[0].value;
        } else {
          dropdownElement.value = '';
        }
      }

      // Trigger change event with the corrected value to ensure consistency
      setTimeout(() => {
        dropdownElement.dispatchEvent(new Event('change', { bubbles: true }));
      }, 10);

      return; // BLOCK the original selection completely
    }

    // Additional validation: Check if the option is actually available in the current context
    const productData = window.productCardManager?.productDataStore[productId];
    if (productData) {
      const currentSelections = this.getSelectedOptions(dropdownElement.closest('[data-product-id]'));
      const isActuallyAvailable = this.variantManager.isVariantAvailable(optionName, selectedValue, productId, currentSelections);

      if (!isActuallyAvailable) {
        // Find first available option
        const availableOptions = Array.from(dropdownElement.querySelectorAll('option:not([disabled]):not(.unavailable):not([value=""])'));
        if (availableOptions.length > 0) {
          dropdownElement.value = availableOptions[0].value;
        } else {
          dropdownElement.value = '';
        }

        // Trigger change event with the corrected value
        setTimeout(() => {
          dropdownElement.dispatchEvent(new Event('change', { bubbles: true }));
        }, 10);

        return; // BLOCK the original selection completely
      }
    }

    // If selection is valid, proceed with normal flow
    window.productCardManager?.selectVariant(productId, optionName, selectedValue);
  }

  // Get all selected options from the card
  getSelectedOptions(productCard) {
    const selectedOptions = {};

    // Check dropdown selects first
    const selects = productCard.querySelectorAll('select[data-option]');
    selects.forEach(select => {
      if (select.value && select.value !== '') {
        selectedOptions[select.dataset.option] = select.value;
      }
    });

    // Check other option types (swatches, buttons, etc.)
    const optionElements = productCard.querySelectorAll('[data-option][data-value]');
    optionElements.forEach(element => {
      if (element.classList.contains('selected') || element.value) {
        selectedOptions[element.dataset.option] = element.dataset.value || element.value;
      }
    });

    return selectedOptions;
  }

  // Update dependent dropdowns based on current selection
  updateDependentDropdowns(productId, changedOptionName, selectedValue) {
    const productData = window.productCardManager?.productDataStore[productId];
    const productCard = document.querySelector(`[data-product-id="${productId}"]`);

    if (!productData || !productCard) return;

    // Set flag to prevent Swiper reinitialization during dropdown updates
    this.isUpdatingDropdowns = true;

    // Get all dropdown selects
    const allDropdowns = productCard.querySelectorAll('select[data-option]');

    // Process dropdowns in batches to avoid blocking the UI
    const processDropdown = (dropdown, index) => {
      const optionName = dropdown.dataset.option;

      // Skip the dropdown that was just changed
      if (optionName === changedOptionName) return;

      // Get current selection for this dropdown
      const currentSelection = dropdown.value;

      // Find available options for this dropdown based on other selections
      const availableOptions = this.getAvailableOptionsForDropdown(productId, optionName, changedOptionName, selectedValue);

      // Update dropdown options
      this.updateDropdownOptions(dropdown, availableOptions, currentSelection);
    };

    // Process dropdowns with minimal delay to prevent UI blocking
    allDropdowns.forEach((dropdown, index) => {
      setTimeout(() => processDropdown(dropdown, index), index * 10);
    });

    // Reset flag after dropdown updates are complete
    setTimeout(() => {
      this.isUpdatingDropdowns = false;
    }, allDropdowns.length * 10 + 50);
  }

  // Get available options for a specific dropdown based on other selections
  getAvailableOptionsForDropdown(productId, targetOptionName, changedOptionName, changedValue) {
    const productData = window.productCardManager?.productDataStore[productId];
    const productCard = document.querySelector(`[data-product-id="${productId}"]`);

    if (!productData || !productData.variants) return [];

    // Get current selections (excluding the one being changed)
    const currentSelections = this.getSelectedOptions(productCard);

    // Add the changed selection
    currentSelections[changedOptionName] = changedValue;

    // Find all variants that match the current selections (excluding target option)
    const matchingVariants = productData.variants.filter(variant => {
      const variantTitle = variant.title || '';
      const variantOptions = variantTitle.split(' / ');

      return Object.keys(currentSelections).every(optionName => {
        if (optionName === targetOptionName) return true; // Skip target option

        const optionPosition = this.variantManager.getOptionPosition(optionName, productData.options);
        const variantValue = variantOptions[optionPosition - 1];
        const selectedValue = currentSelections[optionName];

        return variantValue === selectedValue;
      });
    });

    // Extract unique values for the target option
    const targetOptionPosition = this.variantManager.getOptionPosition(targetOptionName, productData.options);
    const availableValues = new Set();

    matchingVariants.forEach(variant => {
      const variantTitle = variant.title || '';
      const variantOptions = variantTitle.split(' / ');
      const optionValue = variantOptions[targetOptionPosition - 1];

      if (optionValue && variant.inventory !== 0) { // Only include in-stock options
        availableValues.add(optionValue);
      }
    });

    return Array.from(availableValues);
  }

  // Update dropdown options and disable unavailable ones
  updateDropdownOptions(dropdown, availableOptions, currentSelection) {
    const optionName = dropdown.dataset.option;

    // Add visual feedback
    dropdown.classList.add('updating');

    // Get all options in the dropdown
    const options = dropdown.querySelectorAll('option');

    options.forEach(option => {
      if (option.value === '') return; // Skip the "Select..." option

      const isAvailable = availableOptions.includes(option.value);

      if (isAvailable) {
        option.disabled = false;
        option.style.display = 'block';
        option.style.color = '';
        option.style.opacity = '1';
        option.classList.remove('unavailable');
        option.removeAttribute('disabled');
        option.style.pointerEvents = 'auto';
        option.style.visibility = 'visible';
      } else {
        option.disabled = true;
        option.setAttribute('disabled', 'disabled');
        option.style.display = 'none'; // Hide unavailable options
        option.style.visibility = 'hidden';
        option.style.color = '#ccc';
        option.style.opacity = '0.5';
        option.style.pointerEvents = 'none';
        option.classList.add('unavailable');
      }
    });

    // If current selection is no longer available, reset to first available option
    if (currentSelection && !availableOptions.includes(currentSelection)) {
      const firstAvailable = availableOptions[0];
      if (firstAvailable) {
        dropdown.value = firstAvailable;

        // Trigger the selection logic
        const productId = dropdown.closest('[data-product-id]')?.dataset.productId;
        if (productId) {
          window.productCardManager?.selectVariant(productId, optionName, firstAvailable);
        }
      } else {
        dropdown.value = '';
      }
    }

    // Remove visual feedback
    setTimeout(() => {
      dropdown.classList.remove('updating');
    }, 100);

    // Add event listener to prevent selection of disabled options
    const productId = dropdown.closest('[data-product-id]')?.dataset.productId;
    if (productId) {
      this.addDropdownValidation(dropdown, productId);
    }
  }

  // Add validation event listener to dropdown
  addDropdownValidation(dropdown, productId) {
    // Remove existing listener if any
    dropdown.removeEventListener('change', dropdown._validationHandler);
    dropdown.removeEventListener('input', dropdown._validationHandler);

    // Create new validation handler
    dropdown._validationHandler = (event) => {
      const selectedValue = event.target.value;
      const selectedOption = event.target.querySelector(`option[value="${selectedValue}"]`);

      if (selectedOption && (selectedOption.disabled || selectedOption.classList.contains('unavailable'))) {
        event.preventDefault();
        event.stopPropagation();

        // Force revert immediately
        const productCard = document.querySelector(`[data-product-id="${productId}"]`);
        const currentSelections = this.getSelectedOptions(productCard);
        const optionName = dropdown.dataset.option;
        const previousValue = currentSelections[optionName];

        if (previousValue && !dropdown.querySelector(`option[value="${previousValue}"]`)?.disabled) {
          dropdown.value = previousValue;
        } else {
          // Find first available option
          const availableOptions = Array.from(dropdown.querySelectorAll('option:not([disabled]):not(.unavailable):not([value=""])'));
          if (availableOptions.length > 0) {
            dropdown.value = availableOptions[0].value;
          } else {
            dropdown.value = '';
          }
        }

        return false;
      }
    };

    // Add event listeners for both change and input events
    dropdown.addEventListener('change', dropdown._validationHandler);
    dropdown.addEventListener('input', dropdown._validationHandler);

    // Add mousedown prevention for disabled options
    dropdown.addEventListener('mousedown', (event) => {
      const target = event.target;
      if (target.tagName === 'OPTION' && (target.disabled || target.classList.contains('unavailable'))) {
        event.preventDefault();
        event.stopPropagation();
        return false;
      }
    });

    // Add click prevention for disabled options
    dropdown.addEventListener('click', (event) => {
      const target = event.target;
      if (target.tagName === 'OPTION' && (target.disabled || target.classList.contains('unavailable'))) {
        event.preventDefault();
        event.stopPropagation();
        return false;
      }
    });
  }
}

// Export for use in other files
window.DropdownManager = DropdownManager;
