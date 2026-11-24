/**
 * Vitest tests for ChatAssistant component.
 * Covers: rendering, quick prompts, user input, loading state,
 * error state, accessibility attributes, and keyboard interaction.
 */
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ChatAssistant } from "@/components/assistant/chat-assistant";

// ─── Mock fetch ──────────────────────────────────────────────────────────────

const mockSuccessResponse = {
  answer: "It is safe to exercise. The AQI is 75 — satisfactory.",
  referenced_aqi: 75,
  risk_level: "low",
  approved_actions: ["Keep outdoor workouts to light intensity."],
  scientific_rationale: "PM2.5 within acceptable thresholds.",
  llm_grounded: false,
  disclaimer: "BreatheWise provides environmental guidance only.",
};

function mockFetch(response: object, status = 200) {
  global.fetch = vi.fn().mockResolvedValue({
    ok: status < 400,
    status,
    json: async () => response,
  } as Response);
}

beforeEach(() => {
  vi.clearAllMocks();
});

// ─── Tests ───────────────────────────────────────────────────────────────────

describe("ChatAssistant", () => {
  it("renders welcome message on mount", () => {
    mockFetch(mockSuccessResponse);
    render(<ChatAssistant lat={28.6} lon={77.2} />);
    expect(screen.getByRole("heading", { name: /BreatheWise Assistant/i })).toBeInTheDocument();
    expect(screen.getByText(/evidence-based air quality assistant/i)).toBeInTheDocument();
  });

  it("renders all quick prompt chips", () => {
    mockFetch(mockSuccessResponse);
    render(<ChatAssistant lat={28.6} lon={77.2} />);
    expect(screen.getByLabelText(/Can I exercise outside/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Kids safe/i)).toBeInTheDocument();
  });

  it("shows current AQI in header when provided", () => {
    mockFetch(mockSuccessResponse);
    render(<ChatAssistant lat={28.6} lon={77.2} currentAqi={142} />);
    expect(screen.getByText(/142/)).toBeInTheDocument();
  });

  it("displays user message after submission", async () => {
    mockFetch(mockSuccessResponse);
    const user = userEvent.setup();
    render(<ChatAssistant lat={28.6} lon={77.2} />);
    const input = screen.getByRole("textbox");
    await user.type(input, "Can I jog today?");
    await user.keyboard("{Enter}");
    expect(await screen.findByText("Can I jog today?")).toBeInTheDocument();
  });

  it("displays assistant response after fetch", async () => {
    mockFetch(mockSuccessResponse);
    const user = userEvent.setup();
    render(<ChatAssistant lat={28.6} lon={77.2} />);
    const input = screen.getByRole("textbox");
    await user.type(input, "Is air quality good?");
    await user.keyboard("{Enter}");
    await waitFor(() =>
      expect(
        screen.getByText(/It is safe to exercise/i)
      ).toBeInTheDocument()
    );
  });

  it("shows risk badge in response", async () => {
    mockFetch(mockSuccessResponse);
    const user = userEvent.setup();
    render(<ChatAssistant lat={28.6} lon={77.2} />);
    const input = screen.getByRole("textbox");
    await user.type(input, "AQI today?");
    await user.keyboard("{Enter}");
    await waitFor(() =>
      expect(screen.getByText(/AQI 75/i)).toBeInTheDocument()
    );
  });

  it("shows error message on fetch failure", async () => {
    mockFetch({ detail: "Service unavailable" }, 503);
    const user = userEvent.setup();
    render(<ChatAssistant lat={28.6} lon={77.2} />);
    const input = screen.getByRole("textbox");
    await user.type(input, "Is it safe?");
    await user.keyboard("{Enter}");
    await waitFor(() =>
      expect(screen.getByRole("alert")).toBeInTheDocument()
    );
  });

  it("send button is disabled when input is empty", () => {
    mockFetch(mockSuccessResponse);
    render(<ChatAssistant lat={28.6} lon={77.2} />);
    const sendBtn = screen.getByRole("button", { name: /send message/i });
    expect(sendBtn).toBeDisabled();
  });

  it("send button is enabled when input has text", async () => {
    mockFetch(mockSuccessResponse);
    const user = userEvent.setup();
    render(<ChatAssistant lat={28.6} lon={77.2} />);
    const input = screen.getByRole("textbox");
    await user.type(input, "Hello");
    const sendBtn = screen.getByRole("button", { name: /send message/i });
    expect(sendBtn).not.toBeDisabled();
  });

  it("message list has correct ARIA role", () => {
    mockFetch(mockSuccessResponse);
    render(<ChatAssistant lat={28.6} lon={77.2} />);
    expect(screen.getByRole("list", { name: /Conversation history/i })).toBeInTheDocument();
  });

  it("input has accessible label via sr-only", () => {
    mockFetch(mockSuccessResponse);
    render(<ChatAssistant lat={28.6} lon={77.2} />);
    expect(screen.getByLabelText(/Ask BreatheWise/i)).toBeInTheDocument();
  });

  it("quick prompt button sends query without typing", async () => {
    mockFetch(mockSuccessResponse);
    render(<ChatAssistant lat={28.6} lon={77.2} />);
    const chip = screen.getByLabelText(/Quick question.*exercise/i);
    fireEvent.click(chip);
    await waitFor(() =>
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/assistant/chat",
        expect.objectContaining({ method: "POST" })
      )
    );
  });

  it("clears input after sending", async () => {
    mockFetch(mockSuccessResponse);
    const user = userEvent.setup();
    render(<ChatAssistant lat={28.6} lon={77.2} />);
    const input = screen.getByRole("textbox") as HTMLTextAreaElement;
    await user.type(input, "Test query");
    await user.keyboard("{Enter}");
    expect(input.value).toBe("");
  });
});
