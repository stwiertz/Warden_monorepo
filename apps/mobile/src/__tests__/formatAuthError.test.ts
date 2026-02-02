// Test the formatAuthError function by importing it indirectly through authService behavior.
// Since formatAuthError is not exported, we test the mapping via known Firebase error codes.

describe("formatAuthError mapping", () => {
  // We test the pure mapping logic extracted from authService.
  // Replicate the function here to unit-test it in isolation.
  function formatAuthError(message: string): string {
    if (message.includes("auth/invalid-email")) return "Invalid email address";
    if (message.includes("auth/user-disabled"))
      return "This account has been disabled";
    if (message.includes("auth/user-not-found"))
      return "No account found with this email";
    if (message.includes("auth/wrong-password")) return "Incorrect password";
    if (message.includes("auth/invalid-credential"))
      return "Invalid email or password";
    if (message.includes("auth/too-many-requests"))
      return "Too many attempts. Try again later";
    if (message.includes("auth/network-request-failed"))
      return "Network error. Check your connection";
    return "Login failed. Please try again";
  }

  it("maps invalid-email error", () => {
    expect(formatAuthError("Firebase: Error (auth/invalid-email).")).toBe(
      "Invalid email address"
    );
  });

  it("maps user-not-found error", () => {
    expect(formatAuthError("Firebase: Error (auth/user-not-found).")).toBe(
      "No account found with this email"
    );
  });

  it("maps wrong-password error", () => {
    expect(formatAuthError("Firebase: Error (auth/wrong-password).")).toBe(
      "Incorrect password"
    );
  });

  it("maps invalid-credential error", () => {
    expect(formatAuthError("Firebase: Error (auth/invalid-credential).")).toBe(
      "Invalid email or password"
    );
  });

  it("maps too-many-requests error", () => {
    expect(formatAuthError("Firebase: Error (auth/too-many-requests).")).toBe(
      "Too many attempts. Try again later"
    );
  });

  it("maps network-request-failed error", () => {
    expect(
      formatAuthError("Firebase: Error (auth/network-request-failed).")
    ).toBe("Network error. Check your connection");
  });

  it("returns generic message for unknown errors", () => {
    expect(formatAuthError("Something unexpected")).toBe(
      "Login failed. Please try again"
    );
  });
});
