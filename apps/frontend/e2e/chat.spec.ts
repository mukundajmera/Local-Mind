import { test, expect } from './fixtures/fixtures';

/**
 * Chat Panel UI Tests
 * 
 * Test suite for the Cognitive Stream (Chat) interface.
 * Uses Page Object Model pattern for maintainability.
 * 
 * User Flows Tested:
 * 1. Initial page load and welcome message display
 * 2. Sending a message and receiving AI response
 * 3. Input validation (empty message prevention)
 * 4. Keyboard navigation (Enter to send)
 * 5. Quick action buttons visibility
 */

test.describe('Chat Panel - Core Functionality', () => {

    test.beforeEach(async ({ chatPage }) => {
        // Navigate to the application before each test
        await chatPage.goto();
    });

    test('should display chat panel on page load', async ({ chatPage }) => {
        // Verify the main chat panel elements are visible
        await chatPage.expectPanelVisible();
        await chatPage.expectQuickActionsVisible();
    });

    test('should show welcome message on initial load', async ({ chatPage }) => {
        // The welcome message should be the first message displayed
        await chatPage.expectWelcomeMessage();

        // Should only have one message initially
        const messageCount = await chatPage.getMessageCount();
        expect(messageCount).toBe(1);
    });

    test('should have send button disabled when input is empty', async ({ chatPage }) => {
        // Send button should be disabled with empty input
        await chatPage.expectSendButtonDisabled();
    });

    test('should enable send button when input has text', async ({ chatPage }) => {
        // Type a message
        await chatPage.chatInput.fill('Hello, how are you?');

        // Send button should now be enabled
        await chatPage.expectSendButtonEnabled();
    });

});

test.describe('Chat Panel - Message Sending', () => {

    test.beforeEach(async ({ chatPage }) => {
        await chatPage.goto();
    });

    test('should send message and receive AI response', async ({ chatPage }) => {
        const testMessage = 'What is quantum computing?';

        // Get initial message count
        const initialCount = await chatPage.getMessageCount();

        // Send a message
        await chatPage.sendMessage(testMessage);

        // User message should appear immediately
        const afterSendCount = await chatPage.getMessageCount();
        expect(afterSendCount).toBe(initialCount + 1);

        // Wait for AI response
        await chatPage.waitForResponse();

        // Should now have user message + AI response
        const finalCount = await chatPage.getMessageCount();
        expect(finalCount).toBe(initialCount + 2);

        // Last message should be from assistant
        const lastMessage = chatPage.getLastMessage();
        await expect(lastMessage).toHaveAttribute('data-role', 'assistant');
    });

    test('should send message using Enter key', async ({ chatPage }) => {
        const testMessage = 'Testing Enter key submission';

        const initialCount = await chatPage.getMessageCount();

        // Send message with Enter key
        await chatPage.sendMessageWithEnter(testMessage);

        // Message should be sent
        const afterSendCount = await chatPage.getMessageCount();
        expect(afterSendCount).toBe(initialCount + 1);

        // The user message should contain the test text
        const userMessages = chatPage.getUserMessages();
        await expect(userMessages.last()).toContainText(testMessage);
    });

    test('should clear input after sending message', async ({ chatPage }) => {
        await chatPage.chatInput.fill('Test message');
        await chatPage.sendButton.click();

        // Input should be cleared after sending
        await expect(chatPage.chatInput).toHaveValue('');
    });

    test('should show loading indicator while waiting for response', async ({ chatPage }) => {
        await chatPage.chatInput.fill('Trigger loading state');
        await chatPage.sendButton.click();

        // Loading indicator should appear
        await expect(chatPage.loadingIndicator).toBeVisible();

        // Wait for response (loading should disappear)
        await chatPage.waitForResponse();

        // Loading indicator should be gone
        await expect(chatPage.loadingIndicator).not.toBeVisible();
    });

    test('should disable send button while loading', async ({ chatPage }) => {
        await chatPage.chatInput.fill('First message');
        await chatPage.sendButton.click();

        // Send button should be disabled during loading
        await expect(chatPage.sendButton).toBeDisabled();

        // Wait for response to complete
        await chatPage.waitForResponse();
    });

});

test.describe('Chat Panel - Message Display', () => {

    test.beforeEach(async ({ chatPage }) => {
        await chatPage.goto();
    });

    test('should display user messages aligned to the right', async ({ chatPage }) => {
        await chatPage.sendMessage('Right-aligned message');

        const userMessage = chatPage.getUserMessages().last();

        // User messages have justify-end class which aligns to right
        await expect(userMessage).toHaveClass(/justify-end/);
    });

    test('should display assistant messages aligned to the left', async ({ chatPage }) => {
        // Welcome message is from assistant
        const assistantMessage = chatPage.getMessageById('welcome');

        // Assistant messages have justify-start class which aligns to left
        await expect(assistantMessage).toHaveClass(/justify-start/);
    });

    test('should display timestamps on messages', async ({ chatPage }) => {
        await chatPage.sendMessage('Message with timestamp');
        await chatPage.waitForResponse();

        // User message should have a timestamp
        const userMessage = chatPage.getUserMessages().last();
        const timestamp = userMessage.locator('p').last(); // Timestamp is the last <p> element

        await expect(timestamp).toBeVisible();
        // Timestamp format: HH:MM (e.g., "07:45 PM" or "--:--")
        await expect(timestamp).toHaveText(/\d{2}:\d{2}|--:--/);
    });

});

test.describe('Chat Panel - Quick Actions', () => {

    test.beforeEach(async ({ chatPage }) => {
        await chatPage.goto();
    });

    test('should display all quick action buttons', async ({ chatPage }) => {
        await chatPage.expectQuickActionsVisible();
    });

    test('quick action: Generate Podcast button should be clickable', async ({ chatPage }) => {
        await expect(chatPage.generatePodcastButton).toBeEnabled();
        await expect(chatPage.generatePodcastButton).toContainText('Generate Podcast');
    });

    test('quick action: Summarize All button should be clickable', async ({ chatPage }) => {
        await expect(chatPage.summarizeAllButton).toBeEnabled();
        await expect(chatPage.summarizeAllButton).toContainText('Summarize All');
    });

    test('quick action: Deep Dive button should be clickable', async ({ chatPage }) => {
        await expect(chatPage.deepDiveButton).toBeEnabled();
        await expect(chatPage.deepDiveButton).toContainText('Deep Dive');
    });

});

test.describe('Chat Panel - Edge Cases', () => {

    test.beforeEach(async ({ chatPage }) => {
        await chatPage.goto();
    });

    test('should not send empty message', async ({ chatPage }) => {
        const initialCount = await chatPage.getMessageCount();

        // Try to send empty message by pressing Enter on empty input
        await chatPage.chatInput.press('Enter');

        // Message count should remain the same
        const afterCount = await chatPage.getMessageCount();
        expect(afterCount).toBe(initialCount);
    });

    test('should not send whitespace-only message', async ({ chatPage }) => {
        const initialCount = await chatPage.getMessageCount();

        // Fill with whitespace
        await chatPage.chatInput.fill('   ');

        // Send button should still be disabled
        await chatPage.expectSendButtonDisabled();

        // Message count should remain the same
        const afterCount = await chatPage.getMessageCount();
        expect(afterCount).toBe(initialCount);
    });

    test('should handle multiple messages in sequence', async ({ chatPage }) => {
        const messages = ['First message', 'Second message', 'Third message'];
        const initialCount = await chatPage.getMessageCount();

        for (const msg of messages) {
            await chatPage.sendMessage(msg);
            await chatPage.waitForResponse();
        }

        // Should have initial + (3 user + 3 assistant) messages
        const finalCount = await chatPage.getMessageCount();
        expect(finalCount).toBe(initialCount + 6);
    });

});
