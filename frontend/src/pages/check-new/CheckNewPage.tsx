import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router'
import { Upload, FileText, Type, FolderOpen, Shield, ArrowRight, X, CheckCircle } from 'lucide-react'
import { Button } from '@/shared/ui/Button'
import { useUploadDocumentMutation } from '@/features/documents/hooks'
import { useCreateRuleSetMutation } from '@/features/rulesets/hooks'
import { useCreateCheckTaskMutation } from '@/features/check-tasks/hooks'
import { formatFileSize } from '@/shared/lib/utils'
import { cn } from '@/shared/lib/utils'
import type { RuleSet, FormatRule } from '@/entities/ruleset/model'

type SourceType = 'manual' | 'requirement_doc' | 'template'

const steps = [
  { id: 1, label: '上传论文', desc: '上传待检查的 Word 文档' },
  { id: 2, label: '选择规则来源', desc: '选择或上传格式要求' },
  { id: 3, label: '确认规则', desc: '确认并调整提取的规则' },
  { id: 4, label: '生成报告', desc: '检查并生成格式报告' },
]

const defaultRules: FormatRule[] = [
  {
    id: 'body_font',
    category: 'font',
    target: { scope: 'body.paragraph', selector: '正文' },
    expectation: { fontFamilyEastAsia: '宋体', fontSizePt: 12, bold: false },
    severity: 'major',
    source: { type: 'manual', excerpt: '正文采用宋体小四号字' },
    enabled: true,
  },
  {
    id: 'heading1',
    category: 'heading',
    target: { scope: 'heading.1', selector: '一级标题' },
    expectation: { fontFamilyEastAsia: '黑体', fontSizePt: 16, bold: true },
    severity: 'major',
    source: { type: 'manual', excerpt: '一级标题黑体三号居中' },
    enabled: true,
  },
  {
    id: 'page_margin_top',
    category: 'page',
    target: { scope: 'document', selector: '整篇文档' },
    expectation: { marginTopCm: 2.54 },
    severity: 'minor',
    source: { type: 'manual', excerpt: '页边距上下 2.54cm' },
    enabled: true,
  },
]

export function CheckNewPage() {
  const navigate = useNavigate()
  const [currentStep, setCurrentStep] = useState(1)
  const [uploadedFile, setUploadedFile] = useState<{ document_id: string; filename: string; size_bytes: number } | null>(null)
  const [sourceType, setSourceType] = useState<SourceType | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  const uploadMutation = useUploadDocumentMutation()
  const createRuleSetMutation = useCreateRuleSetMutation()
  const createCheckTaskMutation = useCreateCheckTaskMutation()

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [])

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }, [])

  const handleFile = async (file: File) => {
    if (!file.name.endsWith('.docx')) {
      alert('仅支持 .docx 格式文件')
      return
    }
    if (file.size > 100 * 1024 * 1024) {
      alert('文件大小不能超过 100MB')
      return
    }
    try {
      const result = await uploadMutation.mutateAsync(file)
      setUploadedFile(result)
      setCurrentStep(2)
    } catch (err) {
      alert('上传失败: ' + (err instanceof Error ? err.message : '未知错误'))
    }
  }

  const handleSelectSource = (type: SourceType) => {
    setSourceType(type)
  }

  const handleConfirmRules = async () => {
    if (!uploadedFile || !sourceType) return

    const ruleset: RuleSet = {
      id: `ruleset_${Date.now()}`,
      name: '手动创建规则集',
      source_type: sourceType,
      version: '1.0.0',
      locale: 'zh-CN',
      rules: defaultRules,
      created_at: new Date().toISOString(),
    }

    try {
      const created = await createRuleSetMutation.mutateAsync(ruleset)
      const report = await createCheckTaskMutation.mutateAsync({
        document_id: uploadedFile.document_id,
        ruleset_id: created.id,
      })
      navigate(`/reports/${report.id}`)
    } catch (err) {
      alert('检查失败: ' + (err instanceof Error ? err.message : '未知错误'))
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="flex gap-8">
        {/* Left Step Rail */}
        <div className="hidden md:block w-64 shrink-0">
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
                    <div className={cn('mt-2 h-8 w-px', currentStep > step.id ? 'bg-success-500' : 'bg-neutral-200')} />
                  )}
                </div>
                <div className="pt-1">
                  <div className={cn('text-sm font-medium', currentStep >= step.id ? 'text-neutral-900' : 'text-neutral-400')}>
                    {step.label}
                  </div>
                  <div className="text-xs text-neutral-400 mt-0.5">{step.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 min-w-0">
          <div className="bg-white rounded-xl border border-neutral-200 shadow-sm">
            <div className="p-6 border-b border-neutral-200">
              <h1 className="text-lg font-semibold text-neutral-900">创建检查任务</h1>
              <p className="text-sm text-neutral-500 mt-1">上传论文并选择格式规则进行检查</p>
            </div>

            <div className="p-6 space-y-8">
              {/* Step 1: Upload */}
              <section>
                <div className="flex items-center gap-2 mb-4">
                  <div className={cn('flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold', currentStep >= 1 ? 'bg-primary-600 text-white' : 'bg-neutral-200 text-neutral-500')}>
                    1
                  </div>
                  <h2 className="text-base font-medium text-neutral-900">上传论文</h2>
                </div>

                {!uploadedFile ? (
                  <div
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    className={cn(
                      'relative rounded-xl border-2 border-dashed p-12 text-center transition-colors',
                      isDragging ? 'border-primary-500 bg-primary-50' : 'border-neutral-300 hover:border-neutral-400',
                    )}
                  >
                    <input
                      type="file"
                      accept=".docx"
                      onChange={handleFileInput}
                      className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    />
                    <Upload className="mx-auto h-10 w-10 text-neutral-400" />
                    <p className="mt-4 text-sm font-medium text-neutral-700">拖拽文件到此处，或点击上传</p>
                    <p className="mt-1 text-xs text-neutral-400">仅支持 .docx 格式，文件大小不超过 100MB</p>
                    {uploadMutation.isPending && (
                      <p className="mt-4 text-sm text-primary-600">上传中...</p>
                    )}
                  </div>
                ) : (
                  <div className="flex items-center gap-3 rounded-lg border border-neutral-200 bg-neutral-50 p-4">
                    <FileText className="h-8 w-8 text-primary-600" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-neutral-900 truncate">{uploadedFile.filename}</p>
                      <p className="text-xs text-neutral-500">{formatFileSize(uploadedFile.size_bytes)}</p>
                    </div>
                    <button
                      onClick={() => {
                        setUploadedFile(null)
                        setCurrentStep(1)
                        setSourceType(null)
                      }}
                      className="p-1 rounded-md hover:bg-neutral-200 text-neutral-400"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                )}
              </section>

              {/* Step 2: Source Selection */}
              {currentStep >= 2 && (
                <section>
                  <div className="flex items-center gap-2 mb-4">
                    <div className={cn('flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold', currentStep >= 2 ? 'bg-primary-600 text-white' : 'bg-neutral-200 text-neutral-500')}>
                      2
                    </div>
                    <h2 className="text-base font-medium text-neutral-900">选择规则来源</h2>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    {[
                      { type: 'manual' as SourceType, icon: Type, label: '手动输入要求', desc: '手动输入论文格式要求，系统生成规则' },
                      { type: 'requirement_doc' as SourceType, icon: Upload, label: '上传格式规范', desc: '上传学校/学院发布的格式规范或参考文件' },
                      { type: 'template' as SourceType, icon: FolderOpen, label: '选择模板', desc: '从内置或自定义模板中选择适用的规则集' },
                    ].map((item) => (
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
                        <item.icon className={cn('h-6 w-6', sourceType === item.type ? 'text-primary-600' : 'text-neutral-400')} />
                        <p className="mt-3 text-sm font-medium text-neutral-900">{item.label}</p>
                        <p className="mt-1 text-xs text-neutral-500">{item.desc}</p>
                      </button>
                    ))}
                  </div>

                  {sourceType && (
                    <div className="mt-4 flex items-center gap-2 rounded-lg bg-primary-50 border border-primary-200 p-3">
                      <CheckCircle className="h-4 w-4 text-primary-600" />
                      <span className="text-sm text-primary-700">
                        已选择：{sourceType === 'manual' ? '手动输入要求' : sourceType === 'requirement_doc' ? '上传格式规范' : '选择模板'}
                      </span>
                    </div>
                  )}
                </section>
              )}

              {/* Step 3 & 4: Confirm & Start */}
              {sourceType && (
                <section className="flex items-center justify-between pt-4 border-t border-neutral-200">
                  <div className="flex items-center gap-2 text-sm text-neutral-500">
                    <Shield className="h-4 w-4" />
                    <span>论文正文不发送给外部模型，所有解析与检查均在本地进行</span>
                  </div>
                  <Button
                    onClick={handleConfirmRules}
                    isLoading={createRuleSetMutation.isPending || createCheckTaskMutation.isPending}
                    className="gap-1"
                  >
                    确认并生成报告
                    <ArrowRight className="h-4 w-4" />
                  </Button>
                </section>
              )}
            </div>
          </div>
        </div>

        {/* Right Sidebar */}
        <div className="hidden xl:block w-72 shrink-0">
          <div className="sticky top-24 space-y-4">
            <div className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
              <h3 className="text-sm font-medium text-neutral-900">任务概览</h3>
              <div className="mt-3 space-y-3">
                <div className="flex items-center gap-3">
                  <FileText className="h-5 w-5 text-neutral-400" />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-neutral-500">论文文件</p>
                    <p className="text-sm text-neutral-900 truncate">{uploadedFile?.filename || '未上传'}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <FolderOpen className="h-5 w-5 text-neutral-400" />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-neutral-500">规则来源</p>
                    <p className="text-sm text-neutral-900">
                      {sourceType === 'manual' ? '手动输入' : sourceType === 'requirement_doc' ? '格式规范' : sourceType === 'template' ? '模板' : '未选择'}
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
              <p className="mt-2 text-xs text-neutral-500 leading-relaxed">
                论文正文不发送给外部模型，所有解析与检查均在本地进行。仅提取格式相关信息用于分析。
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
