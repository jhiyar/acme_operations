import { useState } from "react";
import axios from "axios";

import { AdminView } from "../../widgets/AdminView";
import { Button } from "../../widgets/Button";
import { CustomModal } from "../../widgets/CustomModal";
import { useAuth } from "../core/AuthProvider";
import { UserForm } from "./components/UserForm";
import {
  useDeleteUser,
  useUsers,
  type ManagedUser,
} from "./hooks/useUsers";

function UserRow({
  user,
  currentSub,
  onEdit,
  onDelete,
}: {
  user: ManagedUser;
  currentSub?: string;
  onEdit: (userId: string) => void;
  onDelete: (user: ManagedUser) => void;
}) {
  const isSelf = currentSub != null && user.id === currentSub;
  const roleLabel = user.roles.join(", ") || "no app role";

  return (
    <article className="issue-row">
      <div className="issue-row-top">
        <h2>
          {user.username}
          {isSelf ? <span className="issue-id"> · you</span> : null}
        </h2>
        <div className="issue-badges">
          <span className="badge">{roleLabel}</span>
          <span className={`badge ${user.enabled ? "" : "status-open"}`}>
            {user.enabled ? "enabled" : "disabled"}
          </span>
        </div>
      </div>
      <p className="issue-meta">
        {[user.first_name, user.last_name].filter(Boolean).join(" ") || "No name"}
        {user.email ? ` · ${user.email}` : ""}
      </p>

      <div className="issue-manage">
        <button
          type="button"
          className="btn btn-ghost btn-compact"
          onClick={() => onEdit(user.id)}
        >
          Edit
        </button>
        <button
          type="button"
          className="btn btn-ghost btn-compact issue-delete"
          disabled={isSelf}
          title={isSelf ? "You cannot delete your own account" : "Delete user"}
          onClick={() => onDelete(user)}
        >
          Delete
        </button>
      </div>
    </article>
  );
}

function UsersPageContent() {
  const { user } = useAuth();
  const [modalUserId, setModalUserId] = useState<string | null | undefined>(
    undefined,
  );
  const [userToDelete, setUserToDelete] = useState<ManagedUser | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const deleteUser = useDeleteUser();
  const { data, isLoading, isError, error, refetch, isFetching } = useUsers();

  const modalOpen = modalUserId !== undefined;
  const isCreate = modalUserId === null;

  const closeDeleteDialog = () => {
    if (deleteUser.isPending) {
      return;
    }
    setUserToDelete(null);
    setDeleteError(null);
    deleteUser.reset();
  };

  return (
    <div className="issues-page">
      <section className="issues-content">
        <header className="issues-header">
          <div className="issues-header-main">
            <h1>Users</h1>
            <div className="issues-header-controls">
              <button
                type="button"
                className="btn btn-ghost btn-compact"
                onClick={() => void refetch()}
                disabled={isFetching}
              >
                Refresh
              </button>
              <button
                type="button"
                className="btn btn-primary btn-compact"
                onClick={() => setModalUserId(null)}
              >
                New user
              </button>
            </div>
          </div>
          <p className="muted issues-subtitle">
            Manage Keycloak identities and realm roles for Acme Operations. ·{" "}
            {data?.count ?? 0} users
          </p>
        </header>

        {isLoading ? <p className="muted">Loading users…</p> : null}
        {isError ? (
          <p className="error">
            {error instanceof Error ? error.message : "Failed to load users"}
          </p>
        ) : null}

        {!isLoading && data && data.users.length === 0 ? (
          <div className="chat-empty">
            <p>No users found.</p>
            <p className="muted">Create a user or check Keycloak connectivity.</p>
          </div>
        ) : null}

        <div className="issue-list">
          {data?.users.map((managed) => (
            <UserRow
              key={managed.id}
              user={managed}
              currentSub={user?.sub}
              onEdit={(userId) => setModalUserId(userId)}
              onDelete={setUserToDelete}
            />
          ))}
        </div>
      </section>

      <CustomModal
        open={modalOpen}
        title={isCreate ? "New user" : `Edit user`}
        onClose={() => setModalUserId(undefined)}
      >
        <UserForm
          id={modalUserId}
          onCancel={() => setModalUserId(undefined)}
          onSuccess={() => setModalUserId(undefined)}
        />
      </CustomModal>

      <CustomModal
        open={userToDelete != null}
        title="Delete user"
        onClose={closeDeleteDialog}
      >
        {userToDelete ? (
          <div className="confirm-dialog">
            <p>
              Delete Keycloak user “{userToDelete.username}”? They will no longer
              be able to sign in.
            </p>
            {deleteError ? <p className="error">{deleteError}</p> : null}
            <div className="issue-form-actions">
              <Button
                type="button"
                variant="ghost"
                disabled={deleteUser.isPending}
                onClick={closeDeleteDialog}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="danger"
                disabled={deleteUser.isPending}
                onClick={() => {
                  setDeleteError(null);
                  deleteUser.mutate(userToDelete.id, {
                    onSuccess: () => {
                      setUserToDelete(null);
                      deleteUser.reset();
                    },
                    onError: (err) => {
                      if (axios.isAxiosError(err)) {
                        const detail = err.response?.data?.detail;
                        setDeleteError(
                          typeof detail === "string"
                            ? detail
                            : "Delete failed — try again.",
                        );
                        return;
                      }
                      setDeleteError("Delete failed — try again.");
                    },
                  });
                }}
              >
                {deleteUser.isPending ? "Deleting…" : "Delete"}
              </Button>
            </div>
          </div>
        ) : null}
      </CustomModal>
    </div>
  );
}

export function UsersPage() {
  return (
    <AdminView redirect>
      <UsersPageContent />
    </AdminView>
  );
}
