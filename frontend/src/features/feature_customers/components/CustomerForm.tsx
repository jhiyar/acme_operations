import { useEffect, useState } from "react";
import axios from "axios";
import { useForm } from "react-hook-form";

import { Button } from "../../../widgets/Button";
import { TextField } from "../../../widgets/TextField";
import {
  useCreateCustomer,
  useCustomers,
  useUpdateCustomer,
  type Customer,
} from "../hooks/useCustomers";

type CustomerFormValues = {
  name: string;
  industry: string;
  tier: string;
  account_owner: string;
  contact_email: string;
  notes: string;
};

type CustomerFormProps = {
  /** Present = edit; absent/null = create */
  id?: number | null;
  onSuccess?: () => void;
  onCancel?: () => void;
};

const TIER_OPTIONS = [
  { value: "standard", label: "Standard" },
  { value: "premium", label: "Premium" },
  { value: "enterprise", label: "Enterprise" },
];

const EMPTY_VALUES: CustomerFormValues = {
  name: "",
  industry: "",
  tier: "standard",
  account_owner: "",
  contact_email: "",
  notes: "",
};

function valuesFromCustomer(customer: Customer): CustomerFormValues {
  return {
    name: customer.name,
    industry: customer.industry ?? "",
    tier: customer.tier || "standard",
    account_owner: customer.account_owner ?? "",
    contact_email: customer.contact_email ?? "",
    notes: customer.notes ?? "",
  };
}

export function CustomerForm({ id, onSuccess, onCancel }: CustomerFormProps) {
  const isEdit = id != null;
  const { data, isLoading } = useCustomers(true);
  const createCustomer = useCreateCustomer();
  const updateCustomer = useUpdateCustomer();
  const [submitError, setSubmitError] = useState<string | null>(null);

  const existing = isEdit
    ? data?.customers.find((customer) => customer.id === id)
    : undefined;

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CustomerFormValues>({
    defaultValues: EMPTY_VALUES,
  });

  useEffect(() => {
    if (isEdit && existing) {
      reset(valuesFromCustomer(existing));
      return;
    }
    if (!isEdit) {
      reset(EMPTY_VALUES);
    }
  }, [isEdit, existing, reset]);

  const busy =
    isSubmitting || createCustomer.isPending || updateCustomer.isPending;
  const loadingCustomer = isEdit && (isLoading || (!existing && !data));

  const onSubmit = handleSubmit(async (values) => {
    setSubmitError(null);
    const payload = {
      name: values.name.trim(),
      industry: values.industry.trim(),
      tier: values.tier.trim() || "standard",
      account_owner: values.account_owner.trim(),
      contact_email: values.contact_email.trim(),
      notes: values.notes.trim(),
    };

    try {
      if (isEdit && id != null) {
        await updateCustomer.mutateAsync({ customerId: id, ...payload });
      } else {
        await createCustomer.mutateAsync(payload);
      }
      onSuccess?.();
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const detail = err.response?.data?.detail;
        setSubmitError(
          typeof detail === "string"
            ? detail
            : err.message || "Unable to save customer",
        );
        return;
      }
      setSubmitError(
        err instanceof Error ? err.message : "Unable to save customer",
      );
    }
  });

  if (loadingCustomer) {
    return <p className="muted">Loading customer…</p>;
  }

  if (isEdit && !existing && data) {
    return <p className="error">Customer #{id} was not found.</p>;
  }

  return (
    <form className="issue-form" onSubmit={onSubmit} noValidate>
      <TextField
        label="Name"
        error={errors.name?.message}
        disabled={busy}
        {...register("name", { required: "Name is required" })}
      />

      <div className="issue-form-row">
        <TextField
          label="Industry"
          disabled={busy}
          {...register("industry")}
        />
        <label className="text-field" htmlFor="customer-tier">
          <span>Tier</span>
          <select id="customer-tier" disabled={busy} {...register("tier")}>
            {TIER_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="issue-form-row">
        <TextField
          label="Account owner"
          disabled={busy}
          placeholder="username"
          {...register("account_owner")}
        />
        <TextField
          label="Contact email"
          type="email"
          disabled={busy}
          error={errors.contact_email?.message}
          {...register("contact_email", {
            pattern: {
              value: /^$|^[^\s@]+@[^\s@]+\.[^\s@]+$/,
              message: "Enter a valid email",
            },
          })}
        />
      </div>

      <label className="text-field" htmlFor="customer-notes">
        <span>Notes</span>
        <textarea
          id="customer-notes"
          rows={4}
          disabled={busy}
          {...register("notes")}
        />
      </label>

      {submitError ? <p className="form-error">{submitError}</p> : null}

      <div className="issue-form-actions">
        {onCancel ? (
          <Button type="button" variant="ghost" disabled={busy} onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
        <Button type="submit" disabled={busy}>
          {busy ? "Saving…" : isEdit ? "Save changes" : "Create customer"}
        </Button>
      </div>
    </form>
  );
}
