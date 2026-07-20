import { useState } from "react";
import axios from "axios";

import { Button } from "../../widgets/Button";
import { CustomModal } from "../../widgets/CustomModal";
import {
  ADMIN_ROLES,
  PermissionCheck,
  useHasRole,
} from "../../widgets/PermissionCheck";
import { CustomerForm } from "./components/CustomerForm";
import {
  useCustomers,
  useDeleteCustomer,
  type Customer,
} from "./hooks/useCustomers";

function CustomerRow({
  customer,
  onEdit,
  onDelete,
}: {
  customer: Customer;
  onEdit: (customerId: number) => void;
  onDelete: (customer: Customer) => void;
}) {
  return (
    <article className="issue-row">
      <div className="issue-row-top">
        <h2>
          <span className="issue-id">#{customer.id}</span> {customer.name}
        </h2>
        <div className="issue-badges">
          <span className="badge">{customer.tier || "standard"}</span>
        </div>
      </div>
      <p className="issue-meta">
        {[customer.industry || null, customer.account_owner ? `owner ${customer.account_owner}` : null]
          .filter(Boolean)
          .join(" · ") || "No industry or owner set"}
        {customer.contact_email ? ` · ${customer.contact_email}` : ""}
      </p>
      {customer.notes ? <p className="issue-desc">{customer.notes}</p> : null}

      <PermissionCheck roles={ADMIN_ROLES}>
        <div className="issue-manage">
          <button
            type="button"
            className="btn btn-ghost btn-compact"
            onClick={() => onEdit(customer.id)}
          >
            Edit
          </button>
          <button
            type="button"
            className="btn btn-ghost btn-compact issue-delete"
            onClick={() => onDelete(customer)}
          >
            Delete
          </button>
        </div>
      </PermissionCheck>
    </article>
  );
}

export function CustomersPage() {
  const isAdmin = useHasRole(ADMIN_ROLES);
  const [modalCustomerId, setModalCustomerId] = useState<
    number | null | undefined
  >(undefined);
  const [customerToDelete, setCustomerToDelete] = useState<Customer | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const deleteCustomer = useDeleteCustomer();
  const { data, isLoading, isError, error, refetch, isFetching } = useCustomers();

  const modalOpen = modalCustomerId !== undefined;
  const isCreate = modalCustomerId === null;

  const closeDeleteDialog = () => {
    if (deleteCustomer.isPending) {
      return;
    }
    setCustomerToDelete(null);
    setDeleteError(null);
    deleteCustomer.reset();
  };

  return (
    <div className="issues-page">
      <section className="issues-content">
        <header className="issues-header">
          <div className="issues-header-main">
            <h1>Customers</h1>
            <div className="issues-header-controls">
              <button
                type="button"
                className="btn btn-ghost btn-compact"
                onClick={() => void refetch()}
                disabled={isFetching}
              >
                Refresh
              </button>
              <PermissionCheck roles={ADMIN_ROLES}>
                <button
                  type="button"
                  className="btn btn-primary btn-compact"
                  onClick={() => setModalCustomerId(null)}
                >
                  New customer
                </button>
              </PermissionCheck>
            </div>
          </div>
          <p className="muted issues-subtitle">
            {isAdmin
              ? "Admin view — create, edit, and delete customer profiles."
              : "Customer directory (read-only for sales and support)."}{" "}
            · {data?.count ?? 0} customers
          </p>
        </header>

        {isLoading ? <p className="muted">Loading customers…</p> : null}
        {isError ? (
          <p className="error">
            {error instanceof Error ? error.message : "Failed to load customers"}
          </p>
        ) : null}

        {!isLoading && data && data.customers.length === 0 ? (
          <div className="chat-empty">
            <p>No customers yet.</p>
            <p className="muted">
              {isAdmin
                ? "Add a customer profile to start linking issues."
                : "Ask an admin to add customer profiles."}
            </p>
          </div>
        ) : null}

        <div className="issue-list">
          {data?.customers.map((customer) => (
            <CustomerRow
              key={customer.id}
              customer={customer}
              onEdit={(customerId) => setModalCustomerId(customerId)}
              onDelete={setCustomerToDelete}
            />
          ))}
        </div>
      </section>

      <PermissionCheck roles={ADMIN_ROLES}>
        <CustomModal
          open={modalOpen}
          title={isCreate ? "New customer" : `Edit customer #${modalCustomerId}`}
          onClose={() => setModalCustomerId(undefined)}
        >
          <CustomerForm
            id={modalCustomerId}
            onCancel={() => setModalCustomerId(undefined)}
            onSuccess={() => setModalCustomerId(undefined)}
          />
        </CustomModal>

        <CustomModal
          open={customerToDelete != null}
          title="Delete customer"
          onClose={closeDeleteDialog}
        >
          {customerToDelete ? (
            <div className="confirm-dialog">
              <p>
                Delete customer #{customerToDelete.id} “{customerToDelete.name}”?
                Customers with linked issues cannot be removed until those issues
                are deleted or reassigned.
              </p>
              {deleteError ? <p className="error">{deleteError}</p> : null}
              <div className="issue-form-actions">
                <Button
                  type="button"
                  variant="ghost"
                  disabled={deleteCustomer.isPending}
                  onClick={closeDeleteDialog}
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  variant="danger"
                  disabled={deleteCustomer.isPending}
                  onClick={() => {
                    setDeleteError(null);
                    deleteCustomer.mutate(customerToDelete.id, {
                      onSuccess: () => {
                        setCustomerToDelete(null);
                        deleteCustomer.reset();
                      },
                      onError: (err) => {
                        if (axios.isAxiosError(err)) {
                          const detail = err.response?.data?.detail;
                          setDeleteError(
                            typeof detail === "string"
                              ? detail
                              : "Delete failed — check permissions and try again.",
                          );
                          return;
                        }
                        setDeleteError(
                          "Delete failed — check permissions and try again.",
                        );
                      },
                    });
                  }}
                >
                  {deleteCustomer.isPending ? "Deleting…" : "Delete"}
                </Button>
              </div>
            </div>
          ) : null}
        </CustomModal>
      </PermissionCheck>
    </div>
  );
}
