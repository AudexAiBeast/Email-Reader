export async function graphqlQuery(query, variables = {}) {
  const res = await fetch("/graphql", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, variables }),
  });
  if (!res.ok) {
    throw new Error(`GraphQL request failed: ${res.status}`);
  }
  const json = await res.json();
  if (json.errors && json.errors.length) {
    throw new Error(json.errors.map((e) => e.message).join("; "));
  }
  return json.data;
}

export async function listFtpDir(path) {
  const res = await fetch(`/api/ftp/list?path=${encodeURIComponent(path)}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `FTP list failed: ${res.status}`);
  }
  return res.json();
}

export function ftpFileUrl(path, disposition = "inline") {
  return `/api/ftp/file?path=${encodeURIComponent(path)}&disposition=${disposition}`;
}
