import { type Page, type Locator, expect } from '@playwright/test';

/**
 * Page Object Model for the Chat Panel
 * 
 * Encapsulates all interactions with the cognitive stream chat interface.
 * Uses data-testid attributes for stable, maintainable selectors.
 */
export class ChatPage {
    readonly page: Page;

    // ===== Locators (using stable data-testid attributes) =====

    /** The main chat panel container */
    readonly chatPanel: Locator;

    /** Chat panel header */
    readonly chatHeader: Locator;

    /** Messages container (scrollable area) */
    readonly messagesContainer: Locator;

    /** Chat input textarea */
    readonly chatInput: Locator;

    /** Send message button */
    readonly sendButton: Locator;

    /** Loading indicator (typing dots) */
    readonly loadingIndicator: Locator;

    // Quick action buttons
    readonly generatePodcastButton: Locator;
    readonly summarizeAllButton: Locator;
    readonly deepDiveButton: Locator;

    constructor(page: Page) {
        this.page = page;

        // Initialize locators using data-testid (most stable selector strategy)
        this.chatPanel = page.getByTestId('chat-panel');
        this.chatHeader = page.getByTestId('chat-header');
        this.messagesContainer = page.getByTestId('chat-messages');
        this.chatInput = page.getByTestId('chat-input');
        this.sendButton = page.getByTestId('send-button');
        this.loadingIndicator = page.getByTestId('loading-indicator');

        // Quick action buttons
        this.generatePodcastButton = page.getByTestId('quick-action-podcast');
        this.summarizeAllButton = page.getByTestId('quick-action-summarize');
        this.deepDiveButton = page.getByTestId('quick-action-deepdive');
    }

    // ===== Navigation =====

    /**
     * Navigate to the main workspace page
     */
    async goto(): Promise<void> {
        await this.page.goto('/');
        // Wait for chat panel to be visible and hydrated
        await this.chatPanel.waitFor({ state: 'visible' });
    }

    // ===== Message Actions =====

    /**
     * Send a message in the chat
     * @param message - The message text to send
     */
    async sendMessage(message: string): Promise<void> {
        await this.chatInput.fill(message);
        await this.sendButton.click();
    }

    /**
     * Send a message using Enter key
     * @param message - The message text to send
     */
    async sendMessageWithEnter(message: string): Promise<void> {
        await this.chatInput.fill(message);
        await this.chatInput.press('Enter');
    }

    /**
     * Wait for the AI response to appear (loading indicator to disappear)
     */
    async waitForResponse(): Promise<void> {
        // First wait for loading indicator to appear
        await this.loadingIndicator.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {
            // Loading might be too fast to catch, that's okay
        });
        // Then wait for it to disappear
        await this.loadingIndicator.waitFor({ state: 'hidden', timeout: 10000 });
    }

    // ===== Message Queries =====

    /**
     * Get all message elements
     */
    getAllMessages(): Locator {
        return this.messagesContainer.locator('[data-testid^="message-"]');
    }

    /**
     * Get all user messages
     */
    getUserMessages(): Locator {
        return this.messagesContainer.locator('[data-role="user"]');
    }

    /**
     * Get all assistant messages
     */
    getAssistantMessages(): Locator {
        return this.messagesContainer.locator('[data-role="assistant"]');
    }

    /**
     * Get a specific message by its ID
     * @param id - The message ID
     */
    getMessageById(id: string): Locator {
        return this.page.getByTestId(`message-${id}`);
    }

    /**
     * Get the last message in the chat
     */
    getLastMessage(): Locator {
        return this.getAllMessages().last();
    }

    /**
     * Get the count of all messages
     */
    async getMessageCount(): Promise<number> {
        return this.getAllMessages().count();
    }

    // ===== Assertions (built-in for convenience) =====

    /**
     * Assert that the chat panel is visible and loaded
     */
    async expectPanelVisible(): Promise<void> {
        await expect(this.chatPanel).toBeVisible();
        await expect(this.chatHeader).toContainText('Cognitive Stream');
    }

    /**
     * Assert that the welcome message is displayed
     */
    async expectWelcomeMessage(): Promise<void> {
        const welcomeMessage = this.getMessageById('welcome');
        await expect(welcomeMessage).toBeVisible();
        await expect(welcomeMessage).toContainText('Sovereign Cognitive Engine');
    }

    /**
     * Assert the send button is disabled (no input or loading)
     */
    async expectSendButtonDisabled(): Promise<void> {
        await expect(this.sendButton).toBeDisabled();
    }

    /**
     * Assert the send button is enabled
     */
    async expectSendButtonEnabled(): Promise<void> {
        await expect(this.sendButton).toBeEnabled();
    }

    /**
     * Assert that the last message contains specific text
     * @param text - Text to look for in the last message
     */
    async expectLastMessageContains(text: string): Promise<void> {
        await expect(this.getLastMessage()).toContainText(text);
    }

    /**
     * Assert that quick action buttons are visible
     */
    async expectQuickActionsVisible(): Promise<void> {
        await expect(this.generatePodcastButton).toBeVisible();
        await expect(this.summarizeAllButton).toBeVisible();
        await expect(this.deepDiveButton).toBeVisible();
    }
}
