import { useEffect, useState } from "react";
import axios from "axios";
import { useForm } from "react-hook-form";

import { Button } from "../../../widgets/Button";
import { TextField } from "../../../widgets/TextField";
import {
  useCreateUser,
  useUpdateUser,
  useUsers,
  type ManagedUser,
} from "../hooks/useUsers";

type UserFormValues = {
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  password: string;
  role: string;
  enabled: boolean;
};

type UserFormProps = {
  /** Present = edit; absent/null = create */
  id?: string | null;
  onSuccess?: () => void;
  onCancel?: () => void;
};

const ROLE_OPTIONS = [
  { value: "sales_user", label: "Sales" },
  { value: "support_user", label: "Support" },
  { value: "admin", label: "Admin" },
];

const EMPTY_VALUES: UserFormValues = {
  username: "",
  email: "",
  first_name: "",
  last_name: "",
  password: "",
  role: "sales_user",
  enabled: true,
};

function valuesFromUser(user: ManagedUser): UserFormValues {
  return {
    username: user.username,
    email: user.email ?? "",
    first_name: user.first_name ?? "",
    last_name: user.last_name ?? "",
    password: "",
    role: user.roles[0] || "sales_user",
    enabled: user.enabled,
  };
}

export function UserForm({ id, onSuccess, onCancel }: UserFormProps) {
  const isEdit = id != null;
  const { data, isLoading } = useUsers(true);
  const createUser = useCreateUser();
  const updateUser = useUpdateUser();
  const [submitError, setSubmitError] = useState<string | null>(null);

  const existing = isEdit
    ? data?.users.find((user) => user.id === id)
    : undefined;

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<UserFormValues>({
    defaultValues: EMPTY_VALUES,
  });

  useEffect(() => {
    if (isEdit && existing) {
      reset(valuesFromUser(existing));
      return;
    }
    if (!isEdit) {
      reset(EMPTY_VALUES);
    }
  }, [isEdit, existing, reset]);

  const busy = isSubmitting || createUser.isPending || updateUser.isPending;
  const loadingUser = isEdit && (isLoading || (!existing && !data));

  const onSubmit = handleSubmit(async (values) => {
    setSubmitError(null);
    try {
      if (isEdit && id != null) {
        const payload: {
          userId: string;
          email: string;
          first_name: string;
          last_name: string;
          role: string;
          enabled: boolean;
          password?: string;
        } = {
          userId: id,
          email: values.email.trim(),
          first_name: values.first_name.trim(),
          last_name: values.last_name.trim(),
          role: values.role,
          enabled: values.enabled,
        };
        if (values.password.trim()) {
          payload.password = values.password;
        }
        await updateUser.mutateAsync(payload);
      } else {
        await createUser.mutateAsync({
          username: values.username.trim(),
          email: values.email.trim(),
          first_name: values.first_name.trim(),
          last_name: values.last_name.trim(),
          password: values.password,
          role: values.role,
          enabled: values.enabled,
        });
      }
      onSuccess?.();
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const detail = err.response?.data?.detail;
        setSubmitError(
          typeof detail === "string"
            ? detail
            : err.message || "Unable to save user",
        );
        return;
      }
      setSubmitError(err instanceof Error ? err.message : "Unable to save user");
    }
  });

  if (loadingUser) {
    return <p className="muted">Loading user…</p>;
  }

  if (isEdit && !existing && data) {
    return <p className="error">User was not found.</p>;
  }

  return (
    <form className="issue-form" onSubmit={onSubmit} noValidate>
      <TextField
        label="Username"
        disabled={busy || isEdit}
        error={errors.username?.message}
        {...register("username", {
          required: isEdit ? false : "Username is required",
        })}
      />

      <div className="issue-form-row">
        <TextField
          label="First name"
          disabled={busy}
          {...register("first_name")}
        />
        <TextField label="Last name" disabled={busy} {...register("last_name")} />
      </div>

      <TextField
        label="Email"
        type="email"
        disabled={busy}
        error={errors.email?.message}
        {...register("email", {
          pattern: {
            value: /^$|^[^\s@]+@[^\s@]+\.[^\s@]+$/,
            message: "Enter a valid email",
          },
        })}
      />

      <div className="issue-form-row">
        <label className="text-field" htmlFor="user-role">
          <span>Role</span>
          <select id="user-role" disabled={busy} {...register("role")}>
            {ROLE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-field checkbox-field" htmlFor="user-enabled">
          <span>Enabled</span>
          <input
            id="user-enabled"
            type="checkbox"
            disabled={busy}
            {...register("enabled")}
          />
        </label>
      </div>

      <TextField
        label={isEdit ? "New password (optional)" : "Password"}
        type="password"
        autoComplete="new-password"
        disabled={busy}
        error={errors.password?.message}
        {...register("password", {
          required: isEdit ? false : "Password is required",
          minLength: { value: 6, message: "At least 6 characters" },
        })}
      />

      {submitError ? <p className="form-error">{submitError}</p> : null}

      <div className="issue-form-actions">
        {onCancel ? (
          <Button type="button" variant="ghost" disabled={busy} onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
        <Button type="submit" disabled={busy}>
          {busy ? "Saving…" : isEdit ? "Save changes" : "Create user"}
        </Button>
      </div>
    </form>
  );
}
