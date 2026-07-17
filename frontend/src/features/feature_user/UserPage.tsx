import { useForm } from "react-hook-form";

import { Button } from "../../widgets/Button";
import { PageHeader } from "../../widgets/PageHeader";

type UserFormValues = {
  name: string;
  email: string;
};

export function UserPage() {
  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<UserFormValues>();

  const onSubmit = (values: UserFormValues) => {
    console.log("user form", values);
    reset();
  };

  return (
    <section>
      <PageHeader title="Users" subtitle="Example feature using React Hook Form." />
      <form className="stack-form" onSubmit={handleSubmit(onSubmit)}>
        <label>
          Name
          <input {...register("name", { required: "Name is required" })} />
          {errors.name ? <span className="error">{errors.name.message}</span> : null}
        </label>
        <label>
          Email
          <input
            type="email"
            {...register("email", { required: "Email is required" })}
          />
          {errors.email ? (
            <span className="error">{errors.email.message}</span>
          ) : null}
        </label>
        <Button type="submit">Save user</Button>
      </form>
    </section>
  );
}
