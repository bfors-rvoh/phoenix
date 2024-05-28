import React, { useCallback, useMemo, useRef } from "react";
import { graphql, usePaginationFragment } from "react-relay";
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { css } from "@emotion/react";

import { selectableTableCSS } from "@phoenix/components/table/styles";
import { TableEmpty } from "@phoenix/components/table/TableEmpty";
import { TextCell } from "@phoenix/components/table/TextCell";

import type { DatasetExamplesTableFragment$key } from "./__generated__/DatasetExamplesTableFragment.graphql";
import type {
  datasetLoaderQuery,
  datasetLoaderQuery$data,
} from "./__generated__/datasetLoaderQuery.graphql";

const PAGE_SIZE = 100;

export function DatasetExamplesTable({
  dataset,
}: {
  dataset: datasetLoaderQuery$data["dataset"];
}) {
  const tableContainerRef = useRef<HTMLDivElement>(null);
  const { data, loadNext, hasNext, isLoadingNext } = usePaginationFragment<
    datasetLoaderQuery,
    DatasetExamplesTableFragment$key
  >(
    graphql`
      fragment DatasetExamplesTableFragment on Dataset
      @refetchable(queryName: "DatasetExamplesTableQuery")
      @argumentDefinitions(
        after: { type: "String", defaultValue: null }
        first: { type: "Int", defaultValue: 100 }
      ) {
        examples(first: $first, after: $after)
          @connection(key: "DatasetExamplesTable_examples") {
          edges {
            node {
              id
              input
              output
              metadata
            }
          }
        }
      }
    `,
    dataset
  );
  const tableData = useMemo(
    () =>
      data.examples.edges.map((edge) => {
        const { id, input, output, metadata } = edge.node;
        return {
          id,
          input: JSON.stringify(input),
          output: JSON.stringify(output),
          metadata: JSON.stringify(metadata),
        };
      }),
    [data]
  );
  type TableRow = (typeof tableData)[number];
  const columns: ColumnDef<TableRow>[] = [
    {
      header: "id",
      accessorKey: "id",
      cell: TextCell,
    },
    {
      header: "input",
      accessorKey: "input",
      cell: TextCell,
    },
    {
      header: "output",
      accessorKey: "output",
      cell: TextCell,
    },
    {
      header: "metadata",
      accessorKey: "metadata",
      cell: TextCell,
    },
  ];
  const table = useReactTable<TableRow>({
    columns,
    data: tableData,
    getCoreRowModel: getCoreRowModel(),
  });
  const rows = table.getRowModel().rows;
  const isEmpty = rows.length === 0;
  const fetchMoreOnBottomReached = useCallback(
    (containerRefElement?: HTMLDivElement | null) => {
      if (containerRefElement) {
        const { scrollHeight, scrollTop, clientHeight } = containerRefElement;
        //once the user has scrolled within 300px of the bottom of the table, fetch more data if there is any
        if (
          scrollHeight - scrollTop - clientHeight < 300 &&
          !isLoadingNext &&
          hasNext
        ) {
          loadNext(PAGE_SIZE);
        }
      }
    },
    [hasNext, isLoadingNext, loadNext]
  );
  return (
    <div
      css={css`
        flex: 1 1 auto;
        overflow: auto;
      `}
      ref={tableContainerRef}
      onScroll={(e) => fetchMoreOnBottomReached(e.target as HTMLDivElement)}
    >
      <table css={selectableTableCSS}>
        <thead>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <th key={header.id}>
                  <div>
                    {flexRender(
                      header.column.columnDef.header,
                      header.getContext()
                    )}
                  </div>
                </th>
              ))}
            </tr>
          ))}
        </thead>
        {isEmpty ? (
          <TableEmpty />
        ) : (
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                {row.getVisibleCells().map((cell) => {
                  return (
                    <td key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        )}
      </table>
    </div>
  );
}