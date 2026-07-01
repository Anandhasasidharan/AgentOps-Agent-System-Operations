{{- define "agentops.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "agentops.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "agentops.labels" -}}
helm.sh/chart: {{ include "agentops.name" . }}-{{ .Chart.Version }}
app.kubernetes.io/name: {{ include "agentops.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "agentops.databaseUrl" -}}
{{- if .Values.database.externalUrl }}
{{- .Values.database.externalUrl }}
{{- else }}
postgresql+asyncpg://{{ .Values.database.postgres.user }}:{{ .Values.database.postgres.password }}@{{ include "agentops.fullname" . }}-postgres:5432/{{ .Values.database.postgres.database }}
{{- end }}
{{- end }}

{{- define "agentops.otelEndpoint" -}}
http://{{ include "agentops.fullname" . }}-slo-platform:8000/v1/traces
{{- end }}
