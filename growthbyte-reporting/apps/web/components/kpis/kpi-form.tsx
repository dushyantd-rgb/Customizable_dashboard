"use client";

import type { KpiCreate, KpiRecord } from "@growthbyte/shared-types";
import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { api, safeErrorMessage } from "../../lib/api-client";

const isoDate = /^\d{4}-\d{2}-\d{2}$/;
const decimal = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/;

const kpiSchema = z
  .object({
    metric_key: z.string().trim().min(1, "Metric key is required."),
    label: z.string().trim().min(1, "Label is required.").max(120, "Label is too long."),
    target_value: z
      .string()
      .trim()
      .refine((value) => value === "" || (decimal.test(value) && Number.isFinite(Number(value))), {
        message: "Target must be a finite decimal.",
      }),
    unit: z.string().trim().min(1, "Unit is required."),
    direction: z.string().trim().min(1, "Direction is required."),
    attribution_level: z.string().trim().min(1, "Attribution level is required."),
    active_from: z.string().regex(isoDate, "Active-from must be a date."),
    active_to: z
      .string()
      .refine((value) => value === "" || isoDate.test(value), "Active-to must be a date."),
  })
  .superRefine((values, context) => {
    if (values.active_to && values.active_to < values.active_from) {
      context.addIssue({
        code: "custom",
        message: "Active-to cannot be before active-from.",
        path: ["active_to"],
      });
    }
  });

type KpiFormValues = z.infer<typeof kpiSchema>;

interface KpiFormProps {
  readonly clientId: string;
  readonly onCancel: () => void;
  readonly onSaved: () => Promise<void>;
  readonly record?: KpiRecord;
}

export function KpiForm({ clientId, onCancel, onSaved, record }: KpiFormProps) {
  const [saveError, setSaveError] = useState<string | null>(null);
  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
  } = useForm<KpiFormValues>({
    resolver: zodResolver(kpiSchema),
    defaultValues: {
      metric_key: record?.metric_key ?? "",
      label: record?.label ?? "",
      target_value: record?.target_value ?? "",
      unit: record?.unit ?? "",
      direction: record?.direction ?? "",
      attribution_level: record?.attribution_level ?? "",
      active_from: record?.active_from ?? new Date().toISOString().slice(0, 10),
      active_to: record?.active_to ?? "",
    },
  });

  async function save(values: KpiFormValues) {
    setSaveError(null);
    const input: KpiCreate = {
      metric_key: values.metric_key.trim(),
      label: values.label.trim(),
      target_value: values.target_value || null,
      unit: values.unit.trim(),
      direction: values.direction.trim(),
      attribution_level: values.attribution_level.trim(),
      active_from: values.active_from,
      active_to: values.active_to || null,
    };
    try {
      if (record) {
        await api.updateKpi(clientId, record.id, input);
      } else {
        await api.createKpi(clientId, input);
      }
      await onSaved();
    } catch (error) {
      setSaveError(safeErrorMessage(error));
    }
  }

  return (
    <section className="border border-growthbyte-black p-6" aria-label="KPI form">
      <h3 className="text-xl font-semibold">{record ? "Edit KPI" : "Add KPI"}</h3>
      <p className="mt-2 text-sm text-growthbyte-black/70">
        Unit, direction, and attribution follow the structural contract; their catalogs remain
        unapproved.
      </p>
      <form className="mt-6 grid gap-5 sm:grid-cols-2" onSubmit={handleSubmit(save)}>
        <KpiField error={errors.metric_key?.message} label="Metric key">
          <input className="form-input" {...register("metric_key")} />
        </KpiField>
        <KpiField error={errors.label?.message} label="Label">
          <input className="form-input" {...register("label")} />
        </KpiField>
        <KpiField error={errors.target_value?.message} label="Target value">
          <input className="form-input" inputMode="decimal" {...register("target_value")} />
        </KpiField>
        <KpiField error={errors.unit?.message} label="Unit">
          <input className="form-input" {...register("unit")} />
        </KpiField>
        <KpiField error={errors.direction?.message} label="Direction">
          <input className="form-input" {...register("direction")} />
        </KpiField>
        <KpiField error={errors.attribution_level?.message} label="Attribution level">
          <input className="form-input" {...register("attribution_level")} />
        </KpiField>
        <KpiField error={errors.active_from?.message} label="Active from">
          <input className="form-input" type="date" {...register("active_from")} />
        </KpiField>
        <KpiField error={errors.active_to?.message} label="Active to (optional)">
          <input className="form-input" type="date" {...register("active_to")} />
        </KpiField>
        {saveError ? (
          <p className="text-sm text-red-800 sm:col-span-2" role="alert">
            {saveError}
          </p>
        ) : null}
        <div className="flex flex-wrap gap-3 sm:col-span-2">
          <button className="primary-button" disabled={isSubmitting} type="submit">
            {isSubmitting ? "Saving…" : record ? "Save KPI" : "Create KPI"}
          </button>
          <button className="secondary-button" onClick={onCancel} type="button">
            Cancel
          </button>
        </div>
      </form>
    </section>
  );
}

function KpiField({
  children,
  error,
  label,
}: Readonly<{ children: React.ReactElement; error?: string; label: string }>) {
  return (
    <label className="grid content-start gap-2 font-medium">
      {label}
      {children}
      {error ? (
        <span className="text-sm font-normal text-red-800" role="alert">
          {error}
        </span>
      ) : null}
    </label>
  );
}
