import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { Button } from "../../widgets/Button";
import { TextField } from "../../widgets/TextField";
import { useAuth } from "../core/AuthProvider";

type LoginForm = {
  username: string;
  password: string;
};

export function LoginPage() {
  const { login, isAuthenticated, isReady } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({
    defaultValues: { username: "", password: "" },
  });

  if (isReady && isAuthenticated) {
    return <Navigate to="/chat" replace />;
  }

  const onSubmit = handleSubmit(async (values) => {
    setError(null);
    try {
      await login(values.username.trim(), values.password);
      const from =
        (location.state as { from?: string } | null)?.from &&
        (location.state as { from?: string }).from !== "/login"
          ? (location.state as { from: string }).from
          : "/chat";
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign in");
    }
  });

  return (
    <div className="login-page">
      <div className="login-atmosphere" aria-hidden="true" />
      <section className="login-panel">
        <p className="brand-mark">Acme Operations</p>
        <h1>Sign in to continue</h1>
        <p className="lede">
          Secure access to the enterprise assistant for sales, support, and
          operations.
        </p>

        <form className="login-form" onSubmit={onSubmit} noValidate>
          <TextField
            label="Username"
            autoComplete="username"
            error={errors.username?.message}
            {...register("username", { required: "Username is required" })}
          />
          <TextField
            label="Password"
            type="password"
            autoComplete="current-password"
            error={errors.password?.message}
            {...register("password", { required: "Password is required" })}
          />

          {error ? <p className="form-error">{error}</p> : null}

          <Button type="submit" disabled={isSubmitting} className="login-submit">
            {isSubmitting ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        <div className="login-hint">
          <p className="muted">Demo accounts</p>
          <ul>
            <li>
              <code>sales</code> / <code>sales123</code>
            </li>
            <li>
              <code>support</code> / <code>support123</code>
            </li>
            <li>
              <code>admin</code> / <code>admin123</code>
            </li>
          </ul>
        </div>
      </section>
    </div>
  );
}
