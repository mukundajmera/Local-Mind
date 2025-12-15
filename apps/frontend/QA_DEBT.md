# QA Debt - Untestable or Broken Features

This document tracks features that are currently untestable or have gaps that prevent proper E2E testing.
Each entry should be addressed in a future sprint.

---

## 0. Light Mode Visibility (FIXED)

**Status:** ✅ Resolved

**Issue:** Many components used hardcoded `text-white/XX` Tailwind classes instead of theme-aware CSS custom properties, causing text to be invisible (white-on-white) in light mode.

**Resolution:** Replaced all `text-white/XX` occurrences with `theme-text-primary`, `theme-text-muted`, and `theme-text-faint` classes that use CSS variables.

---

## 1. Source Checkbox Selection

**Test File:** `e2e/notebook-flow.spec.ts`  
**Test Name:** `should update selected state when clicking source checkbox`  
**Status:** `test.fixme()`

**Issue:** The `SourcesSidebar` component does not implement checkbox-based selection. Instead, clicking anywhere on the source card selects it. This differs from the expected NotebookLM-style multi-select behavior.

**Missing Elements:**
- `<input type="checkbox" data-testid="source-checkbox-{id}" />`
- Visual "selected" checkmark indicator

**Suggested Fix:**
Add a checkbox element to each source card in `components/panels/SourcesSidebar.tsx`:
```tsx
<input
    type="checkbox"
    data-testid={`source-checkbox-${source.id}`}
    checked={selectedSources.includes(source.id)}
    onChange={() => toggleSourceSelection(source.id)}
/>
```

---

## 2. Notes Toggle Button

**Test File:** `e2e/notebook-flow.spec.ts`  
**Test Name:** `should toggle notes sidebar when clicking toggle button`  
**Status:** `test.fixme()`

**Issue:** The notes toggle button in `NotebookHeader.tsx` does not have a `data-testid` attribute, making it difficult to reliably locate for testing.

**Current Code (line 53-66 in NotebookHeader.tsx):**
```tsx
<button
    onClick={onToggleNotes}
    className={cn(...)}
    title={isNotesOpen ? "Hide notes" : "Show notes"}
>
    ...
</button>
```

**Suggested Fix:**
Add `data-testid="toggle-notes-btn"` to the button:
```tsx
<button
    onClick={onToggleNotes}
    data-testid="toggle-notes-btn"
    ...
>
```

---

## 3. Chat Message Pin Button

**Test File:** `e2e/notebook-flow.spec.ts`  
**Test Name:** `should pin a chat message when clicking pin button`  
**Status:** `test.fixme()`

**Issue:** The `ChatPanel` component does not have a "Pin" button on individual chat messages. The pinning functionality exists in `NotesSidebar` for notes, but not for chat messages.

**Missing Elements:**
- Pin button on chat message bubbles: `data-testid="pin-msg-{id}"`
- "Pinned" visual indicator on messages

**Suggested Fix:**
If pinning chat messages is a desired feature, add a pin button to the message component in `ChatPanel.tsx`:
```tsx
<button
    onClick={() => handlePinMessage(msg.id)}
    data-testid={`pin-msg-${msg.id}`}
    className={msg.isPinned ? 'pinned' : ''}
>
    📌
</button>
```

---

## Summary

| Feature | Affected Test | Blocker | Priority |
|---------|---------------|---------|----------|
| Checkbox Selection | Source Selection | Missing checkbox element | Medium |
| Notes Toggle | Notes & Pinning | Missing `data-testid` | Low |
| Message Pinning | Notes & Pinning | Feature not implemented | Low |
