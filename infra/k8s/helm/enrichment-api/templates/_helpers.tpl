{{/*
Common labels
*/}}
{{- define "enrichment-api.labels" -}}
app: {{ .Chart.Name }}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "enrichment-api.selectorLabels" -}}
app: {{ .Chart.Name }}
{{- end }}

{{/*
Fullname
*/}}
{{- define "enrichment-api.fullname" -}}
{{ .Release.Name }}-{{ .Chart.Name }}
{{- end }}
