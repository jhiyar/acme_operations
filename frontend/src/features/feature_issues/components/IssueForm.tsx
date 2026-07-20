import { useEffect, useState } from "react";
import axios from "axios";
import { useForm } from "react-hook-form";

import { Button } from "../../../widgets/Button";
import { TextField } from "../../../widgets/TextField";
import { useCustomers } from "../../feature_customers/hooks/useCustomers";
import {
  useCreateIssue,
  useUpdateIssue,
} from "../hooks/useIssueMutations";
import { useIssues, type Issue } from "../hooks/useIssues";

type IssueFormValues = {
  customer_id: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  assigned_to: string;
};

type IssueFormProps = {
  /** Present = edit; absent/null = create */
  id?: number | null;
  onSuccess?: () => void;
  onCancel?: () => void;
};

const STATUS_OPTIONS = [
  { value: "open", label: "Open" },
  { value: "in_progress", label: "In progress" },
  { value: "resolved", label: "Resolved" },
  { value: "closed", label: "Closed" },
];

const PRIORITY_OPTIONS = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "critical", label: "Critical" },
];

const EMPTY_VALUES: IssueFormValues = {
  customer_id: "",
  title: "",
  description: "",
  status: "open",
  priority: "medium",
  assigned_to: "",
};

function valuesFromIssue(issue: Issue): IssueFormValues {
  return {
    customer_id: String(issue.customer.id),
    title: issue.title,
    description: issue.description ?? "",
    status: issue.status,
    priority: issue.priority,
    assigned_to: issue.assigned_to ?? "",
  };
}

export function IssueForm({ id, onSuccess, onCancel }: IssueFormProps) {
  const isEdit = id != null;
  const { data: customersData, isLoading: customersLoading } = useCustomers(true);
  const { data: issuesData, isLoading: issuesLoading } = useIssues();
  const createIssue = useCreateIssue();
  const updateIssue = useUpdateIssue();
  const [submitError, setSubmitError] = useState<string | null>(null);

  const existing = isEdit
    ? issuesData?.issues.find((issue) => issue.id === id)
    : undefined;

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<IssueFormValues>({
    defaultValues: EMPTY_VALUES,
  });

  useEffect(() => {
    if (isEdit && existing) {
      reset(valuesFromIssue(existing));
      return;
    }
    if (!isEdit) {
      reset(EMPTY_VALUES);
    }
  }, [isEdit, existing, reset]);

  const busy =
    isSubmitting || createIssue.isPending || updateIssue.isPending;
  const loadingIssue = isEdit && (issuesLoading || (!existing && !issuesData));

  const onSubmit = handleSubmit(async (values) => {
    setSubmitError(null);
    const customerId = Number(values.customer_id);
    if (!customerId) {
      setSubmitError("Customer is required");
      return;
    }

    try {
      if (isEdit && id != null) {
        await updateIssue.mutateAsync({
          issueId: id,
          customer_id: customerId,
          title: values.title.trim(),
          description: values.description.trim(),
          status: values.status,
          priority: values.priority,
          assigned_to: values.assigned_to.trim(),
        });
      } else {
        await createIssue.mutateAsync({
          customer_id: customerId,
          title: values.title.trim(),
          description: values.description.trim(),
          status: values.status,
          priority: values.priority,
          assigned_to: values.assigned_to.trim(),
        });
      }
      onSuccess?.();
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const detail = err.response?.data?.detail;
        setSubmitError(
          typeof detail === "string"
            ? detail
            : err.message || "Unable to save issue",
        );
        return;
      }
      setSubmitError(
        err instanceof Error ? err.message : "Unable to save issue",
      );
    }
  });

  if (loadingIssue) {
    return <p className="muted">Loading issue…</p>;
  }

  if (isEdit && !existing && issuesData) {
    return <p className="error">Issue #{id} was not found.</p>;
  }

  return (
    <form className="issue-form" onSubmit={onSubmit} noValidate>
      <label className="text-field" htmlFor="issue-customer">
        <span>Customer</span>
        <select
          id="issue-customer"
          disabled={busy || customersLoading}
          {...register("customer_id", { required: "Customer is required" })}
        >
          <option value="">
            {customersLoading ? "Loading customers…" : "Select a customer"}
          </option>
          {customersData?.customers.map((customer) => (
            <option key={customer.id} value={customer.id}>
              {customer.name}
            </option>
          ))}
        </select>
        {errors.customer_id ? (
          <span className="field-error">{errors.customer_id.message}</span>
        ) : null}
      </label>

      <TextField
        label="Title"
        error={errors.title?.message}
        disabled={busy}
        {...register("title", { required: "Title is required" })}
      />

      <label className="text-field" htmlFor="issue-description">
        <span>Description</span>
        <textarea
          id="issue-description"
          rows={4}
          disabled={busy}
          {...register("description")}
        />
      </label>

      <div className="issue-form-row">
        <label className="text-field" htmlFor="issue-status">
          <span>Status</span>
          <select id="issue-status" disabled={busy} {...register("status")}>
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="text-field" htmlFor="issue-priority">
          <span>Priority</span>
          <select id="issue-priority" disabled={busy} {...register("priority")}>
            {PRIORITY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <TextField
        label="Assigned to"
        disabled={busy}
        placeholder="username"
        {...register("assigned_to")}
      />

      {submitError ? <p className="form-error">{submitError}</p> : null}

      <div className="issue-form-actions">
        {onCancel ? (
          <Button type="button" variant="ghost" disabled={busy} onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
        <Button type="submit" disabled={busy || customersLoading}>
          {busy ? "Saving…" : isEdit ? "Save changes" : "Create issue"}
        </Button>
      </div>
    </form>
  );
}
