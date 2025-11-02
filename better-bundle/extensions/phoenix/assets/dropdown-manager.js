/**
 * DropdownManager - Simplified: Shows all options from API, button updates based on variant inventory
 * No cascading dropdowns - all options are always visible
 */
class DropdownManager {
  constructor() {
    this.isUpdatingDropdowns = false;
  }

  // Handle dropdown change - allow any selection, button will update based on variant
  handleDropdownChange(productId, optionName, dropdownElement) {
    const selectedValue = dropdownElement.value;

    // ✅ Allow any selection - no validation needed
    // Button state will be updated in selectVariant based on matching variant inventory
    if (window.productCardManager) {
      window.productCardManager.selectVariant(productId, optionName, selectedValue);
    }
  }

  // Get all selected options from the card
  getSelectedOptions(productCard) {
    const selectedOptions = {};

    // Check dropdown selects
    const selects = productCard.querySelectorAll('select[data-option]');
    selects.forEach(select => {
      if (select.value && select.value !== '') {
        selectedOptions[select.dataset.option] = select.value;
      }
    });

    // Check other option types (swatches, buttons, etc.) if needed
    const optionElements = productCard.querySelectorAll('[data-option][data-value]');
    optionElements.forEach(element => {
      if (element.classList.contains('selected') || element.value) {
        selectedOptions[element.dataset.option] = element.dataset.value || element.value;
      }
    });

    return selectedOptions;
  }

  // ✅ No cascading dropdowns - show all options always
  updateDependentDropdowns(productId, changedOptionName, selectedValue) {
    // No-op: All options are always visible, no filtering needed
    this.isUpdatingDropdowns = false;
  }
}

// Export for use in other files
window.DropdownManager = DropdownManager;
