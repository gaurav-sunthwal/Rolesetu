'use client';

import { useQuery } from '@tanstack/react-query';

import { Badge, Card, Empty, ErrorNote, Loading, PageHeader } from '@/components/ui';
import { api, errorMessage } from '@/lib/api';
import { formatDateTime } from '@/lib/format';
import type { DomainCatalog } from '@/lib/types';

export default function SkillCatalogsPage() {
  const list = useQuery({
    queryKey: ['admin', 'domain-catalogs'],
    queryFn: () => api<DomainCatalog[]>('/admin/domain-catalogs'),
  });

  return (
    <>
      <PageHeader
        title="Skill catalogs"
        subtitle="One dictionary per field, generated once and reused for every person in that field. A new resume does not rebuild it. Software and data stay in the hand-written list and do not appear here."
      />
      {list.isPending ? <Loading /> : null}
      {list.isError ? <ErrorNote message={errorMessage(list.error)} /> : null}
      {list.data?.length === 0 ? (
        <Empty>No field dictionary has been generated yet.</Empty>
      ) : null}
      <div className="space-y-4">
        {list.data?.map((catalog) => (
          <Card key={catalog.field_key}>
            <div className="flex flex-wrap items-center gap-2 border-b border-zinc-200 px-4 py-3">
              <h2 className="font-bold">{catalog.field_key}</h2>
              <Badge>{catalog.source}</Badge>
              <span className="text-xs text-zinc-500">
                {catalog.created_at ? formatDateTime(catalog.created_at) : '—'}
              </span>
            </div>
            <div className="space-y-3 p-4">
              <p className="flex flex-wrap gap-1.5">
                {catalog.core_skill_names.map((name) => (
                  <Badge key={name}>{name}</Badge>
                ))}
              </p>
              <pre className="overflow-x-auto rounded-lg bg-zinc-50 p-3 text-xs leading-5 whitespace-pre-wrap text-zinc-800">
                {catalog.catalog_text}
              </pre>
            </div>
          </Card>
        ))}
      </div>
    </>
  );
}
