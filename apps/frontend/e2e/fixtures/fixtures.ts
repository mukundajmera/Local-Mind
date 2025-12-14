import { test as base } from '@playwright/test';
import { ChatPage } from '../pages/ChatPage';

/**
 * Custom fixtures for Local-Mind tests
 * 
 * Extends Playwright's base test with pre-configured page objects.
 * This provides type-safe, reusable fixtures across all test files.
 */

// Declare the custom fixtures
type LocalMindFixtures = {
    chatPage: ChatPage;
};

// Extend base test with our fixtures
export const test = base.extend<LocalMindFixtures>({
    chatPage: async ({ page }, use) => {
        const chatPage = new ChatPage(page);
        await use(chatPage);
    },
});

// Re-export expect for convenience
export { expect } from '@playwright/test';
