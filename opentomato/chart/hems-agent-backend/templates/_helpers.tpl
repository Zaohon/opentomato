{{- define "hems-agent-backend.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "hems-agent-backend.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "hems-agent-backend.labels" -}}
app.kubernetes.io/name: {{ include "hems-agent-backend.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
