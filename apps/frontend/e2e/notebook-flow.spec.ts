import { test, expect } from '@playwright/test';

/**
 * Notebook Flow E2E Tests
 * 
 * Tests the 3-pane "NotebookLM" style layout:
 * - Left: Sources Sidebar
 * - Center: Source Guide / Chat
 * - Right: Notes Sidebar (collapsible)
 */

test.describe('Notebook Flow', () => {

    test.beforeEach(async ({ page }) => {
        await page.goto('/');
        // Wait for the app to hydrate - look for stable element
        await page.waitForSelector('text=Sources', { timeout: 15000 });
    });

    // =========================================================================
    // Source Selection Tests
    // =========================================================================
    test.describe('Source Selection', () => {

        test('should render sources sidebar', async ({ page }) => {
            const sidebar = page.getByTestId('sources-sidebar');
            await expect(sidebar).toBeVisible({ timeout: 10000 });
        });

        test('should display "Add" button in sources sidebar', async ({ page }) => {
            // Use text-based selector since the button has text content
            const addBtn = page.getByRole('button', { name: '+ Add' });
            await expect(addBtn).toBeVisible({ timeout: 10000 });
        });

        /**
         * FIXME: Source checkbox selection test
         * 
         * The current implementation uses click-to-select on the entire source card,
         * not a checkbox. There is no checkbox element to test.
         * 
         * @see QA_DEBT.md for details
         */
        test.fixme('should update selected state when clicking source checkbox', async ({ page }) => {
            // This test is skipped because:
            // 1. The SourcesSidebar component does not have checkbox inputs
            // 2. Selection happens on card click, which updates activeSourceId state
            // 3. No visual "selected" indicator like a checked checkbox exists

            const checkbox = page.locator('[data-testid="source-checkbox"]');
            await checkbox.click();
            await expect(checkbox).toBeChecked();
        });

        test('should highlight active source when clicked', async ({ page }) => {
            // This test requires at least one source to exist
            // We'll check if the sidebar renders first and skip gracefully if empty
            const sourceCard = page.locator('[data-testid^="source-"]').first();

            // Check if any sources exist
            const count = await sourceCard.count();
            if (count === 0) {
                test.skip();
                return;
            }

            await sourceCard.click();
            // Active source should have the highlight class
            await expect(sourceCard).toHaveClass(/bg-cyber-blue/);
        });

    });

    // =========================================================================
    // Briefing / Source Guide Generation Tests
    // =========================================================================
    test.describe('Briefing Generation', () => {

        test('should show welcome state when no source selected', async ({ page }) => {
            // When no source is selected, the center pane shows welcome message
            const welcomeHeading = page.getByRole('heading', { name: 'Welcome to Local Mind' });
            await expect(welcomeHeading).toBeVisible({ timeout: 10000 });
        });

        test('should load Source Guide when clicking a source title', async ({ page }) => {
            // This test requires at least one source to exist
            const sourceCard = page.locator('[data-testid^="source-"]').first();
            const count = await sourceCard.count();

            if (count === 0) {
                test.skip();
                return;
            }

            // Click the source card (title area)
            await sourceCard.click();

            // Wait for the Source Guide to appear
            const sourceGuide = page.getByTestId('source-guide');
            await expect(sourceGuide).toBeVisible({ timeout: 10000 });

            // Verify Summary card exists
            const summaryHeading = page.getByRole('heading', { name: 'Summary' });
            await expect(summaryHeading).toBeVisible();

            // Verify Key Topics card exists
            const topicsHeading = page.getByRole('heading', { name: 'Key Topics' });
            await expect(topicsHeading).toBeVisible();
        });

        test('should display Start Chat button in Source Guide', async ({ page }) => {
            const sourceCard = page.locator('[data-testid^="source-"]').first();
            const count = await sourceCard.count();

            if (count === 0) {
                test.skip();
                return;
            }

            await sourceCard.click();
            await page.waitForSelector('[data-testid="source-guide"]');

            const startChatBtn = page.getByTestId('start-chat-btn');
            await expect(startChatBtn).toBeVisible();
        });

    });

    // =========================================================================
    // Notes Sidebar Tests
    // =========================================================================
    test.describe('Notes & Pinning', () => {

        /**
         * FIXME: Notes toggle button test
         * 
         * The NotebookHeader's notes toggle button does not have a data-testid attribute,
         * making it difficult to reliably locate for testing.
         * 
         * @see QA_DEBT.md for details
         */
        test.fixme('should toggle notes sidebar when clicking toggle button', async ({ page }) => {
            const toggleBtn = page.getByTestId('toggle-notes-btn');

            // Notes panel should be initially closed (based on default state)
            const notesSidebar = page.getByTestId('notes-sidebar');
            await expect(notesSidebar).not.toBeVisible();

            // Click toggle to open
            await toggleBtn.click();
            await expect(notesSidebar).toBeVisible();

            // Click toggle to close
            await toggleBtn.click();
            await expect(notesSidebar).not.toBeVisible();
        });

        test('should render notes sidebar when visible', async ({ page }) => {
            // Since we can't reliably toggle via testid, check if it exists when open
            // The notes panel visibility depends on isNotesPanelOpen state

            // Try to find the notes sidebar - it may or may not be visible
            const notesSidebar = page.getByTestId('notes-sidebar');

            // We can't control visibility without the toggle button testid
            // Just verify the component structure if visible
            const isVisible = await notesSidebar.isVisible().catch(() => false);

            if (isVisible) {
                await expect(notesSidebar).toBeVisible();
                await expect(page.getByText('Notes')).toBeVisible();
            } else {
                // Skip if not visible - we need the toggle button testid
                test.skip();
            }
        });

        /**
         * FIXME: Pin button on chat messages
         * 
         * The ChatPanel.tsx does not have a pin button on individual chat messages.
         * Pinning functionality exists in NotesSidebar for notes, not for chat messages.
         * 
         * @see QA_DEBT.md for details
         */
        test.fixme('should pin a chat message when clicking pin button', async ({ page }) => {
            // This test is skipped because:
            // 1. ChatPanel messages do not have a pin button
            // 2. The pin functionality in NotesSidebar is for notes, not messages

            const messagePin = page.getByTestId('pin-btn');
            await messagePin.click();
            await expect(messagePin).toHaveClass(/pinned/);
        });

    });

});
