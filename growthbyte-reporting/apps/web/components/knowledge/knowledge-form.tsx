"use client";

import * as AlertDialog from "@radix-ui/react-alert-dialog";
import type {
  JsonObject,
  KnowledgeCreate,
  KnowledgeRecord,
  KnowledgeUpdate,
} from "@growthbyte/shared-types";
import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { api, safeErrorMessage } from "../../lib/api-client";

function parseJsonObject(value: string): JsonObject | null {
  try {
    const parsed: unknown = JSON.parse(value);
    if (typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)) {
      return parsed as JsonObject;
    }
  } catch {
    return null;
  }
  return null;
}

const knowledgeSchema = z.object({
  category: z.string().trim().min(1, "Category is required."),
  knowledge_key: z.string().trim().min(1, "Knowledge key is required."),
  status: z.string().trim().min(1, "Status is required."),
  value_text: z.string().min(1, "Value is required.").refine(parseJsonObject, {
    message: "Value must be a valid JSON object.",
  }),
});

type KnowledgeFormValues = z.infer<typeof knowledgeSchema>;

interface KnowledgeFormProps {
  readonly clientId: string;
  readonly record?: KnowledgeRecord;
  readonly onCancel: () => void;
  readonly onSaved: () => Promise<void>;
}

export function KnowledgeForm({ clientId, record, onCancel, onSaved }: KnowledgeFormProps) {
  const [pendingUpdate, setPendingUpdate] = useState<KnowledgeUpdate | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
  } = useForm<KnowledgeFormValues>({
    resolver: zodResolver(knowledgeSchema),
    defaultValues: {
      category: record?.category ?? "",
      knowledge_key: record?.knowledge_key ?? "",
      status: record?.status ?? "draft",
      value_text: record ? JSON.stringify(record.value, null, 2) : '{\n  "value": ""\n}',
    },
  });

  async function save(input: KnowledgeCreate | KnowledgeUpdate) {
    setSaveError(null);
    try {
      if (record) {
        await api.updateKnowledge(clientId, record.id, input);
      } else {
        await api.createKnowledge(clientId, input as KnowledgeCreate);
      }
      await onSaved();
    } catch (error) {
      setSaveError(safeErrorMessage(error));
    }
  }

  async function prepareSave(values: KnowledgeFormValues) {
    const value = parseJsonObject(values.value_text);
    if (value === null) {
      return;
    }
    const input: KnowledgeCreate = {
      category: values.category.trim(),
      knowledge_key: values.knowledge_key.trim(),
      status: values.status.trim(),
      value,
    };
    const valueChanged = record && JSON.stringify(record.value) !== JSON.stringify(value);
    if (valueChanged) {
      setPendingUpdate(input);
      return;
    }
    await save(input);
  }

  return (
    <section
      className="border border-growthbyte-black bg-growthbyte-white p-6"
      aria-label="Knowledge form"
    >
      <h2 className="text-2xl font-semibold">{record ? "Edit knowledge" : "Add knowledge"}</h2>
      {record && record.source_type !== "manual" ? (
        <p className="mt-2 text-sm text-growthbyte-black/70">
          Imported provenance is read-only and will be preserved by this edit.
        </p>
      ) : null}
      <form className="mt-6 grid gap-5" onSubmit={handleSubmit(prepareSave)}>
        <FormField error={errors.category?.message} label="Category">
          <input className="form-input" {...register("category")} />
        </FormField>
        <FormField error={errors.knowledge_key?.message} label="Knowledge key">
          <input className="form-input" {...register("knowledge_key")} />
        </FormField>
        <FormField error={errors.status?.message} label="Status">
          <input className="form-input" {...register("status")} />
        </FormField>
        <FormField error={errors.value_text?.message} label="Value (JSON)">
          <textarea className="form-input min-h-48 font-mono text-sm" {...register("value_text")} />
        </FormField>
        {saveError ? (
          <p className="text-sm text-red-800" role="alert">
            {saveError}
          </p>
        ) : null}
        <div className="flex flex-wrap gap-3">
          <button className="primary-button" disabled={isSubmitting} type="submit">
            {isSubmitting ? "Saving…" : record ? "Save changes" : "Create knowledge"}
          </button>
          <button className="secondary-button" onClick={onCancel} type="button">
            Cancel
          </button>
        </div>
      </form>

      <AlertDialog.Root
        open={pendingUpdate !== null}
        onOpenChange={(open) => !open && setPendingUpdate(null)}
      >
        <AlertDialog.Portal>
          <AlertDialog.Overlay className="fixed inset-0 z-40 bg-growthbyte-black/60" />
          <AlertDialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(32rem,calc(100%-2rem))] -translate-x-1/2 -translate-y-1/2 bg-growthbyte-white p-6 shadow-xl">
            <AlertDialog.Title className="text-xl font-semibold">
              Overwrite this knowledge value?
            </AlertDialog.Title>
            <AlertDialog.Description className="mt-3 leading-6 text-growthbyte-black/75">
              This changes the reporting value in place. Existing source provenance will remain
              unchanged.
            </AlertDialog.Description>
            <div className="mt-6 flex justify-end gap-3">
              <AlertDialog.Cancel asChild>
                <button className="secondary-button" type="button">
                  Keep existing value
                </button>
              </AlertDialog.Cancel>
              <AlertDialog.Action asChild>
                <button
                  className="primary-button"
                  onClick={() => {
                    const input = pendingUpdate;
                    setPendingUpdate(null);
                    if (input) {
                      void save(input);
                    }
                  }}
                  type="button"
                >
                  Overwrite value
                </button>
              </AlertDialog.Action>
            </div>
          </AlertDialog.Content>
        </AlertDialog.Portal>
      </AlertDialog.Root>
    </section>
  );
}

function FormField({
  children,
  error,
  label,
}: Readonly<{ children: React.ReactElement; error?: string; label: string }>) {
  return (
    <label className="grid gap-2 font-medium">
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
