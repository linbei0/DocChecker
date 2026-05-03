import { useCallback, useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { ArrowRight, CheckCircle, FileText, FolderOpen, Shield, Type, Upload, X } from 'lucide-react'
import { Button } from '@/shared/ui/Button'
import {
  useUploadDocumentMutation,
  useUploadRequirementDocumentMutation,
} from '@/features/documents/hooks'
import { useCreateDraftRuleSetMutation, useRuleSetsQuery } from '@/features/rulesets/hooks'
import { formatFileSize } from '@/shared/lib/utils'
import { cn } from '@/shared/lib/utils'
import type { RequirementDocument, UploadedDocument } from '@/entities/document/model'

type SourceType = 'manual' | 'requirement_doc' | 'template'

const MAX_DOCUMENT_SIZE_BYTES = 30 * 1024 * 1024
const MAX_REQUIREMENT_SIZE_BYTES = 20 * 1024 * 1024
const WORD_FILE_ACCEPT = '.doc,.docx'

export function isSupportedWordFilename(filename: string): boolean {
  return /\.docx?$/i.test(filename)
}

const steps = [
  { id: 1, label: '上传论文', desc: '上传待检查的 Word 文档' },
  { id: 2, label: '选择规则来源', desc: '选择或上传格式要求' },
  { id: 3, label: '确认规则', desc: '确认并调整提取的规则' },
  { id: 4, label: '生成报告', desc: '检查并生成格式报告' },
]

export function CheckNewPage() {
  const navigate = useNavigate()
  const [currentStep, setCurrentStep] = useState(1)
  const [uploadedFile, setUploadedFile] = useState<UploadedDocument | null>(null)
  const [sourceType, setSourceType] = useState<SourceType | null>(null)
  const [manualText, setManualText] = useState('')
  const [requirementDocument, setRequirementDocument] = useState<RequirementDocument | null>(null)
  const [selectedTemplateId, setSelectedTemplateId] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const uploadMutation = useUploadDocumentMutation()
  const uploadRequirementMutation = useUploadRequirementDocumentMutation()
  const createDraftMutation = useCreateDraftRuleSetMutation()
  const { data: templates = [], isLoading: isLoadingTemplates } = useRuleSetsQuery()

  const canCreateDraft = useMemo(() => {
    if (!uploadedFile || !sourceType) return false
    if (sourceType === 'manual') return manualText.trim().length > 0
    if (sourceType === 'requirement_doc') return !!requirementDocument
    return !!selectedTemplateId
  }, [manualText, requirementDocument, selectedTemplateId, sourceType, uploadedFile])

  const handleDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    setIsDragging(false)
    const file = event.dataTransfer.files[0]
    if (file) void handleDocumentFile(file)
  }, [])

  const handleDocumentFileInput = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) void handleDocumentFile(file)
  }, [])

  const handleDocumentFile = async (file: File) => {
    setError(null)
    if (!isSupportedWordFilename(file.name)) {
      setError('仅支持 .doc 或 .docx 格式论文文件。')
      return
    }
    if (file.size > MAX_DOCUMENT_SIZE_BYTES) {
      setError('论文文件大小不能超过 30MB。')
      return
    }
    try {
      const result = await uploadMutation.mutateAsync(file)
      setUploadedFile(result)
      setCurrentStep(2)
    } catch (err) {
      setError('上传论文失败：' + (err instanceof Error ? err.message : '未知错误'))
    }
  }

  const handleRequirementFile = async (file: File) => {
    setError(null)
    if (!isSupportedWordFilename(file.name)) {
      setError('仅支持 .doc 或 .docx 格式规范文档。')
      return
    }
    if (file.size > MAX_REQUIREMENT_SIZE_BYTES) {
      setError('格式规范文件大小不能超过 20MB。')
      return
    }
    try {
      const result = await uploadRequirementMutation.mutateAsync(file)
      setRequirementDocument(result)
    } catch (err) {
      setError('上传格式规范失败：' + (err instanceof Error ? err.message : '未知错误'))
    }
  }

  const handleSelectSource = (type: SourceType) => {
    setSourceType(type)
    setError(null)
  }

  const handleCreateDraft = async () => {
    if (!uploadedFile || !sourceType || !canCreateDraft) return
    try {
      const draft = await createDraftMutation.mutateAsync({
        document_id: uploadedFile.document_id,
        source_type: sourceType,
        manual_text: sourceType === 'manual' ? manualText : undefined,
        requirement_document_id:
          sourceType === 'requirement_doc' ? requirementDocument?.id : undefined,
        template_ruleset_id: sourceType === 'template' ? selectedTemplateId : undefined,
      })
      navigate(`/checks/${draft.id}/rules`)
    } catch (err) {
      setError('生成候选规则失败：' + (err instanceof Error ? err.message : '未知错误'))
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="flex gap-8">
        <StepRail currentStep={currentStep} />

        <div className="min-w-0 flex-1">
          <div className="rounded-xl border border-neutral-200 bg-white shadow-sm">
            <div className="border-b border-neutral-200 p-6">
              <h1 className="text-lg font-semibold text-neutral-900">创建检查任务</h1>
              <p className="mt-1 text-sm text-neutral-500">上传论文并选择格式规则进行检查</p>
            </div>

            <div className="space-y-8 p-6">
              {error && (
                <div className="rounded-lg border border-danger-50 bg-danger-50 p-3 text-sm text-danger-600">
                  {error}
                </div>
              )}

              <section>
                <SectionTitle step={1} title="上传论文" active={currentStep >= 1} />
                {!uploadedFile ? (
                  <FileDropzone
                    isDragging={isDragging}
                    isLoading={uploadMutation.isPending}
                    title="拖拽文件到此处，或点击上传"
                    description="支持 .doc 或 .docx 格式，文件大小不超过 30MB"
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onChange={handleDocumentFileInput}
                  />
                ) : (
                  <SelectedFile
                    filename={uploadedFile.filename}
                    sizeBytes={uploadedFile.size_bytes}
                    onRemove={() => {
                      setUploadedFile(null)
                      setCurrentStep(1)
                      setSourceType(null)
                      setRequirementDocument(null)
                      setSelectedTemplateId('')
                    }}
                  />
                )}
              </section>

              {currentStep >= 2 && (
                <section>
                  <SectionTitle step={2} title="选择规则来源" active={currentStep >= 2} />
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                    {sourceItems.map((item) => (
                      <button
                        key={item.type}
                        onClick={() => handleSelectSource(item.type)}
                        className={cn(
                          'relative rounded-xl border p-5 text-left transition-all hover:shadow-sm',
                          sourceType === item.type
                            ? 'border-primary-500 bg-primary-50 ring-1 ring-primary-500'
                            : 'border-neutral-200 bg-white hover:border-neutral-300',
                        )}
                      >
                        <item.icon
                          className={cn(
                            'h-6 w-6',
                            sourceType === item.type ? 'text-primary-600' : 'text-neutral-400',
                          )}
                        />
                        <p className="mt-3 text-sm font-medium text-neutral-900">{item.label}</p>
                        <p className="mt-1 text-xs text-neutral-500">{item.desc}</p>
                      </button>
                    ))}
                  </div>

                  {sourceType === 'manual' && (
                    <div className="mt-4">
                      <label className="text-sm font-medium text-neutral-900">格式要求文本</label>
                      <textarea
                        value={manualText}
                        onChange={(event) => setManualText(event.target.value)}
                        rows={5}
                        className="mt-2 w-full rounded-lg border border-neutral-200 p-3 text-sm outline-none transition focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20"
                        placeholder="例如：正文宋体小四，1.5倍行距，首行缩进2字符，页边距上下2.5cm。"
                      />
                    </div>
                  )}

                  {sourceType === 'requirement_doc' && (
                    <div className="mt-4">
                      {!requirementDocument ? (
                        <label className="block rounded-xl border border-dashed border-neutral-300 p-6 text-center transition hover:border-primary-400">
                          <input
                            type="file"
                            accept={WORD_FILE_ACCEPT}
                            className="hidden"
                            onChange={(event) => {
                              const file = event.target.files?.[0]
                              if (file) void handleRequirementFile(file)
                            }}
                          />
                          <Upload className="mx-auto h-8 w-8 text-neutral-400" />
                          <p className="mt-3 text-sm font-medium text-neutral-700">
                            上传学校/学院格式规范 .doc 或 .docx
                          </p>
                          <p className="mt-1 text-xs text-neutral-400">文件大小不超过 20MB</p>
                          {uploadRequirementMutation.isPending && (
                            <p className="mt-3 text-sm text-primary-600">上传并提取文本中...</p>
                          )}
                        </label>
                      ) : (
                        <SelectedFile
                          filename={requirementDocument.filename}
                          sizeBytes={requirementDocument.size_bytes}
                          onRemove={() => setRequirementDocument(null)}
                        />
                      )}
                    </div>
                  )}

                  {sourceType === 'template' && (
                    <div className="mt-4 rounded-xl border border-neutral-200">
                      {isLoadingTemplates ? (
                        <div className="p-6 text-sm text-neutral-500">加载模板中...</div>
                      ) : templates.length === 0 ? (
                        <div className="p-6 text-sm text-neutral-500">
                          暂无已发布模板。可先使用手动输入或上传格式规范生成规则集。
                        </div>
                      ) : (
                        <div className="divide-y divide-neutral-200">
                          {templates.map((template) => (
                            <label
                              key={template.id}
                              className="flex cursor-pointer items-center gap-3 p-4 hover:bg-neutral-50"
                            >
                              <input
                                type="radio"
                                name="template"
                                value={template.id}
                                checked={selectedTemplateId === template.id}
                                onChange={() => setSelectedTemplateId(template.id)}
                              />
                              <div className="min-w-0 flex-1">
                                <p className="truncate text-sm font-medium text-neutral-900">
                                  {template.name}
                                </p>
                                <p className="text-xs text-neutral-500">
                                  {template.rules.length} 条规则 · v{template.version}
                                </p>
                              </div>
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </section>
              )}

              {sourceType && (
                <section className="flex items-center justify-between border-t border-neutral-200 pt-4">
                  <div className="flex items-center gap-2 text-sm text-neutral-500">
                    <Shield className="h-4 w-4" />
                    <span>论文正文不发送给外部模型，所有解析与检查均在本地进行</span>
                  </div>
                  <Button
                    onClick={handleCreateDraft}
                    isLoading={createDraftMutation.isPending}
                    disabled={!canCreateDraft}
                    className="gap-1"
                  >
                    下一步：确认规则
                    <ArrowRight className="h-4 w-4" />
                  </Button>
                </section>
              )}
            </div>
          </div>
        </div>

        <TaskSummary uploadedFile={uploadedFile} sourceType={sourceType} />
      </div>
    </div>
  )
}

function StepRail({ currentStep }: { currentStep: number }) {
  return (
    <div className="hidden w-64 shrink-0 md:block">
      <div className="sticky top-24 space-y-6">
        {steps.map((step) => (
          <div key={step.id} className="flex gap-3">
            <div className="flex flex-col items-center">
              <div
                className={cn(
                  'flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold',
                  currentStep === step.id
                    ? 'bg-primary-600 text-white'
                    : currentStep > step.id
                      ? 'bg-success-500 text-white'
                      : 'bg-neutral-200 text-neutral-500',
                )}
              >
                {currentStep > step.id ? <CheckCircle className="h-4 w-4" /> : step.id}
              </div>
              {step.id < steps.length && (
                <div
                  className={cn(
                    'mt-2 h-8 w-px',
                    currentStep > step.id ? 'bg-success-500' : 'bg-neutral-200',
                  )}
                />
              )}
            </div>
            <div className="pt-1">
              <div
                className={cn(
                  'text-sm font-medium',
                  currentStep >= step.id ? 'text-neutral-900' : 'text-neutral-400',
                )}
              >
                {step.label}
              </div>
              <div className="mt-0.5 text-xs text-neutral-400">{step.desc}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function SectionTitle({ step, title, active }: { step: number; title: string; active: boolean }) {
  return (
    <div className="mb-4 flex items-center gap-2">
      <div
        className={cn(
          'flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold',
          active ? 'bg-primary-600 text-white' : 'bg-neutral-200 text-neutral-500',
        )}
      >
        {step}
      </div>
      <h2 className="text-base font-medium text-neutral-900">{title}</h2>
    </div>
  )
}

function FileDropzone({
  isDragging,
  isLoading,
  title,
  description,
  onDragOver,
  onDragLeave,
  onDrop,
  onChange,
}: {
  isDragging: boolean
  isLoading: boolean
  title: string
  description: string
  onDragOver: (event: React.DragEvent) => void
  onDragLeave: (event: React.DragEvent) => void
  onDrop: (event: React.DragEvent) => void
  onChange: (event: React.ChangeEvent<HTMLInputElement>) => void
}) {
  return (
    <div
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      className={cn(
        'relative rounded-xl border-2 border-dashed p-12 text-center transition-colors',
        isDragging ? 'border-primary-500 bg-primary-50' : 'border-neutral-300 hover:border-neutral-400',
      )}
    >
      <input
        type="file"
        accept={WORD_FILE_ACCEPT}
        onChange={onChange}
        className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
      />
      <Upload className="mx-auto h-10 w-10 text-neutral-400" />
      <p className="mt-4 text-sm font-medium text-neutral-700">{title}</p>
      <p className="mt-1 text-xs text-neutral-400">{description}</p>
      {isLoading && <p className="mt-4 text-sm text-primary-600">上传中...</p>}
    </div>
  )
}

function SelectedFile({
  filename,
  sizeBytes,
  onRemove,
}: {
  filename: string
  sizeBytes: number
  onRemove: () => void
}) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-neutral-200 bg-neutral-50 p-4">
      <FileText className="h-8 w-8 text-primary-600" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-neutral-900">{filename}</p>
        <p className="text-xs text-neutral-500">{formatFileSize(sizeBytes)}</p>
      </div>
      <button onClick={onRemove} className="rounded-md p-1 text-neutral-400 hover:bg-neutral-200">
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}

function TaskSummary({
  uploadedFile,
  sourceType,
}: {
  uploadedFile: UploadedDocument | null
  sourceType: SourceType | null
}) {
  return (
    <div className="hidden w-72 shrink-0 xl:block">
      <div className="sticky top-24 space-y-4">
        <div className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
          <h3 className="text-sm font-medium text-neutral-900">任务概览</h3>
          <div className="mt-3 space-y-3">
            <div className="flex items-center gap-3">
              <FileText className="h-5 w-5 text-neutral-400" />
              <div className="min-w-0 flex-1">
                <p className="text-xs text-neutral-500">论文文件</p>
                <p className="truncate text-sm text-neutral-900">{uploadedFile?.filename || '未上传'}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <FolderOpen className="h-5 w-5 text-neutral-400" />
              <div className="min-w-0 flex-1">
                <p className="text-xs text-neutral-500">规则来源</p>
                <p className="text-sm text-neutral-900">
                  {sourceType === 'manual'
                    ? '手动输入'
                    : sourceType === 'requirement_doc'
                      ? '格式规范'
                      : sourceType === 'template'
                        ? '模板'
                        : '未选择'}
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2 text-sm text-success-600">
            <Shield className="h-4 w-4" />
            <span className="font-medium">隐私与安全</span>
          </div>
          <p className="mt-2 text-xs leading-relaxed text-neutral-500">
            论文正文不发送给外部模型，所有解析与检查均在本地进行。仅提取格式相关信息用于分析。
          </p>
        </div>
      </div>
    </div>
  )
}

const sourceItems = [
  { type: 'manual' as SourceType, icon: Type, label: '手动输入要求', desc: '输入论文格式要求，系统生成规则' },
  {
    type: 'requirement_doc' as SourceType,
    icon: Upload,
    label: '上传格式规范',
    desc: '上传学校/学院发布的格式规范文件',
  },
  {
    type: 'template' as SourceType,
    icon: FolderOpen,
    label: '选择模板',
    desc: '从已发布规则模板中选择适用规则集',
  },
]
