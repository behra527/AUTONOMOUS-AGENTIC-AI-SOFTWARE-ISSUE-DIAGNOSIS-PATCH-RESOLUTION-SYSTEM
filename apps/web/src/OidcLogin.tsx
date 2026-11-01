import { useEffect, useRef, useState } from "react";
import {
  InMemoryWebStorage,
  UserManager,
  WebStorageStateStore,
} from "oidc-client-ts";

export type OidcConfig = {
  authority: string;
  client_id: string;
  redirect_uri: string;
  scope: string;
};

export default function OidcLogin({
  config,
  onToken,
}: {
  config?: OidcConfig;
  onToken: (token: string) => Promise<void>;
}) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const handled = useRef(false);
  const manager = useRef<UserManager | null>(null);
  if (!manager.current && config?.authority && config.client_id) {
    manager.current = new UserManager({
      ...config,
      response_type: "code", // The library generates and verifies PKCE/state/nonce.
      automaticSilentRenew: false,
      loadUserInfo: false,
      userStore: new WebStorageStateStore({ store: new InMemoryWebStorage() }),
      // Only transient redirect/PKCE state survives the navigation. Tokens stay in memory.
      stateStore: new WebStorageStateStore({ store: window.sessionStorage }),
    });
  }
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (
      handled.current ||
      !manager.current ||
      !(params.has("code") || params.has("error"))
    )
      return;
    handled.current = true;
    setBusy(true);
    manager.current
      .signinRedirectCallback()
      .then(async (user) => {
        window.history.replaceState({}, "", window.location.pathname);
        await onToken(user.access_token);
      })
      .catch(() => {
        window.history.replaceState({}, "", window.location.pathname);
        setError(
          "SSO callback failed. Check the registered redirect URI, provider settings and access-token audience.",
        );
      })
      .finally(() => setBusy(false));
  }, [onToken]);
  return (
    <div className="oidc-login">
      {!manager.current && (
        <div className="notice">
          SSO is not configured. An administrator must set the issuer, client ID
          and registered redirect URI.
        </div>
      )}
      <button
        disabled={busy || !manager.current}
        onClick={async () => {
          setError("");
          setBusy(true);
          try {
            await manager.current!.signinRedirect();
          } catch {
            setError("Could not reach the identity provider.");
            setBusy(false);
          }
        }}
      >
        {busy ? "Signing in…" : "Sign in with your organization"}
      </button>
      <p className="muted">
        Secure authorization code flow with PKCE. Access tokens remain in
        memory.
      </p>
      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
    </div>
  );
}
