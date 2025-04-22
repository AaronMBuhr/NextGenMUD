// Character Creation - Multiclass Selection

// Available character classes
const AVAILABLE_CLASSES = [
    { id: 'fighter', name: 'Fighter', description: 'Masters of combat skilled with weapons and armor.' },
    { id: 'mage', name: 'Mage', description: 'Wielders of arcane magic and powerful spells.' },
    { id: 'rogue', name: 'Rogue', description: 'Stealthy characters skilled at deception and precision strikes.' },
    { id: 'cleric', name: 'Cleric', description: 'Divine spellcasters with healing and support abilities.' }
];

// Maximum number of classes a character can have
const MAX_CLASS_COUNT = 3;

// Character class selection state
let selectedClasses = [];

// Initialize the character creation UI
function initCharacterCreation() {
    renderClassSelection();
    setupEventListeners();
}

// Render the class selection UI
function renderClassSelection() {
    const classSelectionEl = document.getElementById('class-selection');
    if (!classSelectionEl) return;
    
    // Clear existing content
    classSelectionEl.innerHTML = '';
    
    // Create class selection header
    const header = document.createElement('h3');
    header.textContent = 'Select Your Classes (up to 3)';
    classSelectionEl.appendChild(header);
    
    // Create description
    const description = document.createElement('p');
    description.textContent = 'Choose up to three classes in order of priority (primary, secondary, tertiary).';
    classSelectionEl.appendChild(description);
    
    // Create selected classes display
    const selectedClassesEl = document.createElement('div');
    selectedClassesEl.id = 'selected-classes';
    selectedClassesEl.className = 'selected-classes';
    
    // Show currently selected classes
    if (selectedClasses.length > 0) {
        const classLabels = ['Primary', 'Secondary', 'Tertiary'];
        
        selectedClasses.forEach((classId, index) => {
            const classInfo = AVAILABLE_CLASSES.find(c => c.id === classId);
            const classItem = document.createElement('div');
            classItem.className = 'selected-class-item';
            
            classItem.innerHTML = `
                <span class="class-priority">${classLabels[index]}:</span>
                <span class="class-name">${classInfo.name}</span>
                <button class="remove-class" data-index="${index}">✕</button>
            `;
            
            selectedClassesEl.appendChild(classItem);
        });
    } else {
        const noClassesMsg = document.createElement('p');
        noClassesMsg.textContent = 'No classes selected';
        noClassesMsg.className = 'no-classes';
        selectedClassesEl.appendChild(noClassesMsg);
    }
    
    classSelectionEl.appendChild(selectedClassesEl);
    
    // Create available classes section
    const availableClassesEl = document.createElement('div');
    availableClassesEl.className = 'available-classes';
    
    // Header for available classes
    const availableHeader = document.createElement('h4');
    availableHeader.textContent = 'Available Classes';
    availableClassesEl.appendChild(availableHeader);
    
    // Generate class selection options
    AVAILABLE_CLASSES.forEach(classInfo => {
        // Skip already selected classes
        if (selectedClasses.includes(classInfo.id)) return;
        
        const classOption = document.createElement('div');
        classOption.className = 'class-option';
        classOption.dataset.classId = classInfo.id;
        
        classOption.innerHTML = `
            <h5>${classInfo.name}</h5>
            <p>${classInfo.description}</p>
            <button class="select-class" data-class-id="${classInfo.id}" 
                ${selectedClasses.length >= MAX_CLASS_COUNT ? 'disabled' : ''}>
                Select
            </button>
        `;
        
        availableClassesEl.appendChild(classOption);
    });
    
    classSelectionEl.appendChild(availableClassesEl);
    
    // Add continue button
    const continueBtn = document.createElement('button');
    continueBtn.id = 'continue-button';
    continueBtn.textContent = 'Continue';
    continueBtn.disabled = selectedClasses.length === 0;
    continueBtn.className = 'button primary';
    classSelectionEl.appendChild(continueBtn);
}

// Set up event listeners for the UI
function setupEventListeners() {
    const classSelectionEl = document.getElementById('class-selection');
    if (!classSelectionEl) return;
    
    // Listen for class selection
    classSelectionEl.addEventListener('click', event => {
        // Handle selecting a class
        if (event.target.classList.contains('select-class')) {
            const classId = event.target.dataset.classId;
            if (selectedClasses.length < MAX_CLASS_COUNT && !selectedClasses.includes(classId)) {
                selectedClasses.push(classId);
                renderClassSelection();
            }
        }
        
        // Handle removing a class
        if (event.target.classList.contains('remove-class')) {
            const index = parseInt(event.target.dataset.index);
            selectedClasses.splice(index, 1);
            renderClassSelection();
        }
        
        // Handle continue button
        if (event.target.id === 'continue-button') {
            if (selectedClasses.length > 0) {
                submitClassSelection();
            }
        }
    });
}

// Submit the selected classes
function submitClassSelection() {
    // Create data object to send to server
    const classData = {
        class_priority: selectedClasses
    };
    
    // Send data to server via fetch API
    fetch('/api/character/create/classes', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(classData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Proceed to next step
            window.location.href = '/character/create/abilities';
        } else {
            // Show error
            alert('Error: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('An error occurred. Please try again.');
    });
}

// Initialize the UI when the DOM is loaded
document.addEventListener('DOMContentLoaded', initCharacterCreation); 