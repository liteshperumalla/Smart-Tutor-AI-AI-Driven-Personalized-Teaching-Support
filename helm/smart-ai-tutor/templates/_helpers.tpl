{{/*
Expand the name of the chart.
*/}}
{{- define "smart-ai-tutor.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "smart-ai-tutor.fullname" -}}
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

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "smart-ai-tutor.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "smart-ai-tutor.labels" -}}
helm.sh/chart: {{ include "smart-ai-tutor.chart" . }}
{{ include "smart-ai-tutor.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
environment: {{ .Values.global.environment }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "smart-ai-tutor.selectorLabels" -}}
app.kubernetes.io/name: {{ include "smart-ai-tutor.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "smart-ai-tutor.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "smart-ai-tutor.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Backend labels
*/}}
{{- define "smart-ai-tutor.backend.labels" -}}
{{ include "smart-ai-tutor.labels" . }}
app: smart-ai-tutor
component: backend
tier: api
{{- end }}

{{/*
Frontend labels
*/}}
{{- define "smart-ai-tutor.frontend.labels" -}}
{{ include "smart-ai-tutor.labels" . }}
app: smart-ai-tutor
component: frontend
tier: web
{{- end }}

{{/*
PostgreSQL labels
*/}}
{{- define "smart-ai-tutor.postgres.labels" -}}
{{ include "smart-ai-tutor.labels" . }}
app: smart-ai-tutor
component: postgres
tier: database
{{- end }}

{{/*
Redis labels
*/}}
{{- define "smart-ai-tutor.redis.labels" -}}
{{ include "smart-ai-tutor.labels" . }}
app: smart-ai-tutor
component: redis
tier: cache
{{- end }}

{{/*
Image pull secrets
*/}}
{{- define "smart-ai-tutor.imagePullSecrets" -}}
{{- if .Values.image.pullSecrets }}
imagePullSecrets:
{{- range .Values.image.pullSecrets }}
  - name: {{ . }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Full image name for backend
*/}}
{{- define "smart-ai-tutor.backend.image" -}}
{{- $registry := .Values.image.registry }}
{{- $repository := .Values.backend.image.repository }}
{{- $tag := .Values.backend.image.tag | default .Chart.AppVersion }}
{{- if $registry }}
{{- printf "%s/%s:%s" $registry $repository $tag }}
{{- else }}
{{- printf "%s:%s" $repository $tag }}
{{- end }}
{{- end }}

{{/*
Full image name for frontend
*/}}
{{- define "smart-ai-tutor.frontend.image" -}}
{{- $registry := .Values.image.registry }}
{{- $repository := .Values.frontend.image.repository }}
{{- $tag := .Values.frontend.image.tag | default .Chart.AppVersion }}
{{- if $registry }}
{{- printf "%s/%s:%s" $registry $repository $tag }}
{{- else }}
{{- printf "%s:%s" $repository $tag }}
{{- end }}
{{- end }}

{{/*
PostgreSQL host
*/}}
{{- define "smart-ai-tutor.postgres.host" -}}
{{- if .Values.postgres.external.enabled }}
{{- .Values.postgres.external.host }}
{{- else }}
{{- default (printf "%s-postgres" (include "smart-ai-tutor.fullname" .)) .Values.postgresql.host }}
{{- end }}
{{- end }}

{{/*
PostgreSQL port
*/}}
{{- define "smart-ai-tutor.postgres.port" -}}
{{- if .Values.postgres.external.enabled }}
{{- .Values.postgres.external.port | toString }}
{{- else }}
{{- default "5432" .Values.postgresql.port | toString }}
{{- end }}
{{- end }}

{{/*
PostgreSQL database
*/}}
{{- define "smart-ai-tutor.postgres.database" -}}
{{- if .Values.postgres.external.enabled }}
{{- .Values.postgres.external.database }}
{{- else }}
{{- default "smart_tutor" .Values.postgresql.database }}
{{- end }}
{{- end }}

{{/*
PostgreSQL username
*/}}
{{- define "smart-ai-tutor.postgres.username" -}}
{{- if .Values.postgres.external.enabled }}
{{- .Values.postgres.external.username }}
{{- else }}
{{- default "smart_tutor_user" .Values.postgresql.username }}
{{- end }}
{{- end }}

{{/*
Redis host
*/}}
{{- define "smart-ai-tutor.redis.host" -}}
{{- if .Values.redis.external.enabled }}
{{- .Values.redis.external.host }}
{{- else }}
{{- default (printf "%s-redis" (include "smart-ai-tutor.fullname" .)) .Values.redis.host }}
{{- end }}
{{- end }}

{{/*
Redis port
*/}}
{{- define "smart-ai-tutor.redis.port" -}}
{{- if .Values.redis.external.enabled }}
{{- .Values.redis.external.port | toString }}
{{- else }}
{{- default "6379" .Values.redis.port | toString }}
{{- end }}
{{- end }}

{{/*
External Secret target secret name
*/}}
{{- define "smart-ai-tutor.backendSecretName" -}}
{{- default (printf "%s-backend" (include "smart-ai-tutor.fullname" .)) .Values.secrets.backend }}
{{- end }}
