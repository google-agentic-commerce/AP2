// Trusted Surface: presentation only. Assemble and sign run via agent tool (assemble_and_sign_mandates_tool).
export class TrustedSurface {
  /**
   * Simulate biometric auth (stub).
   * Replace with WebAuthn / platform authenticator in production.
   */
  async requestBiometricAuth(): Promise<boolean> {
    return true;
  }
}
