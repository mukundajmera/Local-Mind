import { test, expect } from "@playwright/test";
import path from "path";

/**
 * Upload Flow E2E Tests
 *
 * Verifies the complete upload flow including:
 * - Upload button visibility
 * - Progress bar display during upload
 * - Successful completion state
 * - Error handling
 */

test.describe("Upload Flow", () => {
    test.beforeEach(async ({ page }) => {
        await page.goto("/");
        // Wait for hydration
        await page.waitForSelector('[data-testid="sources-sidebar"]', {
            timeout: 15000,
        });
    });

    test("Upload button (Add) should be visible and clickable", async ({
        page,
    }) => {
        // Find the Add button in sources sidebar
        const addBtn = page.getByTestId("add-source-btn");
        await expect(addBtn).toBeVisible({ timeout: 10000 });
        await expect(addBtn).toBeEnabled();
    });

    test("File input should accept PDF, MD, TXT files", async ({ page }) => {
        // The hidden file input should accept specific extensions
        const fileInput = page.locator('input[type="file"]');
        await expect(fileInput).toHaveAttribute(
            "accept",
            ".pdf,.md,.txt,.docx"
        );
    });

    test("Upload triggers progress bar display", async ({ page }) => {
        // Mock the upload endpoint to respond slowly
        await page.route("**/api/v1/sources/upload", async (route) => {
            // Return 202 with task_id
            await route.fulfill({
                status: 202,
                contentType: "application/json",
                body: JSON.stringify({
                    task_id: "test-task-123",
                    status: "accepted",
                    message: "Upload accepted",
                }),
            });
        });

        // Mock status endpoint to return processing state
        await page.route("**/api/v1/upload/*/status", async (route) => {
            await route.fulfill({
                status: 200,
                contentType: "application/json",
                body: JSON.stringify({
                    status: "processing",
                    progress: 50,
                    stage: "embedding",
                }),
            });
        });

        // Create a test file and upload
        const fileInput = page.locator('input[type="file"]');

        // Use Playwright's file chooser
        const [fileChooser] = await Promise.all([
            page.waitForEvent("filechooser"),
            page.getByTestId("add-source-btn").click(),
        ]);

        // Create a test file buffer
        await fileChooser.setFiles({
            name: "test-document.txt",
            mimeType: "text/plain",
            buffer: Buffer.from("# Test Document\n\nThis is test content."),
        });

        // Progress bar should appear
        const progressBar = page.getByTestId("upload-progress");
        await expect(progressBar).toBeVisible({ timeout: 5000 });
    });

    test("Successful upload shows completion and refreshes sources", async ({
        page,
    }) => {
        let pollCount = 0;

        // Mock upload endpoint
        await page.route("**/api/v1/sources/upload", async (route) => {
            await route.fulfill({
                status: 202,
                contentType: "application/json",
                body: JSON.stringify({
                    task_id: "complete-task-456",
                    status: "accepted",
                }),
            });
        });

        // Mock status endpoint - complete after 2 polls
        await page.route("**/api/v1/upload/*/status", async (route) => {
            pollCount++;
            if (pollCount >= 2) {
                await route.fulfill({
                    status: 200,
                    contentType: "application/json",
                    body: JSON.stringify({
                        status: "completed",
                        progress: 100,
                        doc_id: "new-doc-123",
                    }),
                });
            } else {
                await route.fulfill({
                    status: 200,
                    contentType: "application/json",
                    body: JSON.stringify({
                        status: "processing",
                        progress: 50,
                    }),
                });
            }
        });

        // Mock sources refresh
        await page.route("**/api/v1/sources", async (route) => {
            if (route.request().method() === "GET" && pollCount >= 2) {
                await route.fulfill({
                    status: 200,
                    contentType: "application/json",
                    body: JSON.stringify({
                        sources: [
                            {
                                id: "new-doc-123",
                                title: "test-document.txt",
                                status: "ready",
                            },
                        ],
                    }),
                });
            } else {
                await route.fulfill({
                    status: 200,
                    contentType: "application/json",
                    body: JSON.stringify({ sources: [] }),
                });
            }
        });

        // Trigger upload
        const [fileChooser] = await Promise.all([
            page.waitForEvent("filechooser"),
            page.getByTestId("add-source-btn").click(),
        ]);

        await fileChooser.setFiles({
            name: "test-document.txt",
            mimeType: "text/plain",
            buffer: Buffer.from("Test content for completion test"),
        });

        // Wait for source to appear in list
        await expect(
            page.getByText("test-document.txt")
        ).toBeVisible({ timeout: 10000 });
    });

    test("Failed upload shows error notification", async ({ page }) => {
        // Mock upload endpoint to return error
        await page.route("**/api/v1/sources/upload", async (route) => {
            await route.fulfill({
                status: 202,
                contentType: "application/json",
                body: JSON.stringify({
                    task_id: "failed-task-789",
                    status: "accepted",
                }),
            });
        });

        // Mock status endpoint to return failure
        await page.route("**/api/v1/upload/*/status", async (route) => {
            await route.fulfill({
                status: 200,
                contentType: "application/json",
                body: JSON.stringify({
                    status: "failed",
                    progress: 0,
                    error: "Database connection failed",
                }),
            });
        });

        // Trigger upload
        const [fileChooser] = await Promise.all([
            page.waitForEvent("filechooser"),
            page.getByTestId("add-source-btn").click(),
        ]);

        await fileChooser.setFiles({
            name: "fail-test.txt",
            mimeType: "text/plain",
            buffer: Buffer.from("Content that will fail"),
        });

        // Error should be displayed (red notification)
        await expect(
            page.locator(".text-red-400, .border-red-500\\/20")
        ).toBeVisible({ timeout: 5000 });
    });
});
