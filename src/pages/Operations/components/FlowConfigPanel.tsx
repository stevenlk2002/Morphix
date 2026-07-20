/**
 * FlowConfigPanel — 节点配置面板。
 *
 * 根据节点类型展示不同的配置表单：
 * - settings: 执行客户/群聊区 + 触发规则区
 * - message: 发送内容区（文本/图片/视频/文件/卡片链接 5 tab）
 * - attr: 修改客户标签区
 * - robot: 机器人托管区
 * - runRobot: 运行机器人区
 * - delay: 延迟时间区
 */
import type { SopNode, SopNodeConfig } from '../../../types/sops'

interface FlowConfigPanelProps {
  node: SopNode | null
  onChange: (config: SopNodeConfig) => void
}

/** 渠道选项 */
const CHANNELS = ['企业微信', '微信', '邮件']
const GROUP_CHANNELS = ['企业微信', '微信']
const CONTENT_TABS = [
  { key: 'text', label: '文本' },
  { key: 'image', label: '图片' },
  { key: 'video', label: '视频' },
  { key: 'file', label: '文件' },
  { key: 'card', label: '卡片链接' },
]
const FILTER_TABS = [
  { key: 'dynamic', label: '动态筛选' },
  { key: 'static', label: '静态筛选' },
  { key: 'group', label: '按客户分组筛选' },
]
const GROUP_FILTER_TABS = [
  { key: 'dynamic', label: '动态筛选' },
  { key: 'static', label: '静态筛选' },
]
const TRIGGER_TABS = [
  { key: 'attribute_change', label: '属性变化' },
  { key: 'timed', label: '定时触发' },
  { key: 'periodic', label: '周期触发' },
  { key: 'special', label: '特殊场景' },
]
const GROUP_TRIGGER_TABS = [
  { key: 'timed', label: '定时触发' },
  { key: 'periodic', label: '周期触发' },
]
const PERIOD_OPTIONS = [
  { value: 'daily', label: '每天' },
  { value: 'weekly', label: '每周' },
  { value: 'monthly', label: '每月' },
]

export default function FlowConfigPanel({ node, onChange }: FlowConfigPanelProps) {
  if (!node) {
    return (
      <div className="flow-config-panel">
        <div className="flow-config-empty">
          <p>点击节点查看配置</p>
        </div>
      </div>
    )
  }

  const config = node.config || {}
  const isGroup = node.type === 'group-settings'

  const update = (partial: Partial<SopNodeConfig>) => {
    onChange({ ...config, ...partial })
  }

  const renderSettings = () => {
    const channels = isGroup ? GROUP_CHANNELS : CHANNELS
    const filterTabs = isGroup ? GROUP_FILTER_TABS : FILTER_TABS
    const triggerTabs = isGroup ? GROUP_TRIGGER_TABS : TRIGGER_TABS
    const filterType = (config.filterType as string) || 'dynamic'
    const triggerType = (config.triggerType as string) || 'attribute_change'
    const triggerConfig = (config.triggerConfig || {}) as Record<string, unknown>

    return (
      <div className="flow-config-content">
        {/* 执行客户/群聊区 */}
        <div className="config-section">
          <div className="config-section-title">{isGroup ? '执行群聊' : '执行客户'}</div>

          <div className="config-field">
            <label className="config-label">渠道类型</label>
            <div className="config-btn-group">
              {channels.map((ch) => (
                <button
                  key={ch}
                  type="button"
                  className={`config-btn ${config.channel === ch ? 'config-btn--active' : ''}`}
                  onClick={() => update({ channel: ch as SopNodeConfig['channel'] })}
                >
                  {ch}
                </button>
              ))}
            </div>
          </div>

          <div className="config-field">
            <label className="config-label">客户筛选</label>
            <div className="config-tabs">
              {filterTabs.map((ft) => (
                <button
                  key={ft.key}
                  type="button"
                  className={`config-tab ${filterType === ft.key ? 'config-tab--active' : ''}`}
                  onClick={() => update({ filterType: ft.key as SopNodeConfig['filterType'] })}
                >
                  {ft.label}
                </button>
              ))}
            </div>
          </div>

          {filterType === 'dynamic' && (
            <div className="config-filter-box">
              <div className="config-field">
                <label className="config-label">托管账号</label>
                <select
                  className="config-select"
                  value={config.dynamicFilter?.hostingAccountId || ''}
                  onChange={(e) =>
                    update({
                      dynamicFilter: {
                        ...config.dynamicFilter,
                        hostingAccountId: e.target.value,
                        hostingBotId: config.dynamicFilter?.hostingBotId || '',
                        tagRelation: config.dynamicFilter?.tagRelation || 'and',
                        tagIds: config.dynamicFilter?.tagIds || [],
                      },
                    })
                  }
                >
                  <option value="">请选择托管账号</option>
                  <option value="acc-zhulu">竹绿-健康</option>
                  <option value="acc-hengkang">恒康倍力</option>
                  <option value="acc-fushou">福寿康</option>
                </select>
              </div>
              <div className="config-field">
                <label className="config-label">托管机器人</label>
                <select
                  className="config-select"
                  value={config.dynamicFilter?.hostingBotId || ''}
                  onChange={(e) =>
                    update({
                      dynamicFilter: {
                        ...config.dynamicFilter,
                        hostingBotId: e.target.value,
                        hostingAccountId: config.dynamicFilter?.hostingAccountId || '',
                        tagRelation: config.dynamicFilter?.tagRelation || 'and',
                        tagIds: config.dynamicFilter?.tagIds || [],
                      },
                    })
                  }
                >
                  <option value="">请选择托管机器人</option>
                  <option value="yefengqiu">野风秋大健康机器人</option>
                  <option value="fanfuni">梵芙尼美妆销售机器人</option>
                </select>
              </div>
              <div className="config-field">
                <label className="config-label">标签关系</label>
                <div className="config-btn-group">
                  <button
                    type="button"
                    className={`config-btn ${config.dynamicFilter?.tagRelation === 'and' ? 'config-btn--active' : ''}`}
                    onClick={() =>
                      update({
                        dynamicFilter: {
                          ...config.dynamicFilter,
                          tagRelation: 'and',
                          hostingAccountId: config.dynamicFilter?.hostingAccountId || '',
                          hostingBotId: config.dynamicFilter?.hostingBotId || '',
                          tagIds: config.dynamicFilter?.tagIds || [],
                        },
                      })
                    }
                  >
                    且
                  </button>
                  <button
                    type="button"
                    className={`config-btn ${config.dynamicFilter?.tagRelation === 'or' ? 'config-btn--active' : ''}`}
                    onClick={() =>
                      update({
                        dynamicFilter: {
                          ...config.dynamicFilter,
                          tagRelation: 'or',
                          hostingAccountId: config.dynamicFilter?.hostingAccountId || '',
                          hostingBotId: config.dynamicFilter?.hostingBotId || '',
                          tagIds: config.dynamicFilter?.tagIds || [],
                        },
                      })
                    }
                  >
                    或
                  </button>
                </div>
              </div>
              <div className="config-field">
                <label className="config-label">标签</label>
                <select
                  className="config-select"
                  multiple
                  value={config.dynamicFilter?.tagIds || []}
                  onChange={(e) => {
                    const selected = Array.from(e.target.selectedOptions, (o) => o.value)
                    update({
                      dynamicFilter: {
                        ...config.dynamicFilter,
                        tagIds: selected,
                        hostingAccountId: config.dynamicFilter?.hostingAccountId || '',
                        hostingBotId: config.dynamicFilter?.hostingBotId || '',
                        tagRelation: config.dynamicFilter?.tagRelation || 'and',
                      },
                    })
                  }}
                  size={4}
                >
                  <option value="tag-1">高意向</option>
                  <option value="tag-2">价格咨询</option>
                  <option value="tag-3">预约演示</option>
                  <option value="tag-intent-1">高</option>
                  <option value="tag-intent-2">中</option>
                  <option value="tag-intent-3">低</option>
                </select>
              </div>
              <div className="config-field">
                <label className="config-label">添加时间</label>
                <input
                  type="date"
                  className="config-input"
                  onChange={() => {
                    /* placeholder - 实际连接到后端筛选 */
                  }}
                />
              </div>
            </div>
          )}

          {filterType === 'static' && (
            <div className="config-filter-box">
              <div className="config-field">
                <label className="config-label">选择客户</label>
                <select className="config-select">
                  <option value="">请选择客户</option>
                  <option value="c-cloud">Cloud</option>
                  <option value="c-didi">didi</option>
                  <option value="c-tongtian">通天草-林瞰</option>
                </select>
              </div>
            </div>
          )}

          {filterType === 'group' && (
            <div className="config-filter-box">
              <div className="config-field">
                <label className="config-label">选择客户分组</label>
                <select className="config-select">
                  <option value="">请选择客户分组</option>
                  <option value="g-high-intent">高意向客户</option>
                  <option value="g-618">618大促触达</option>
                  <option value="g-sleep">沉睡唤醒</option>
                </select>
              </div>
            </div>
          )}

          <div className="config-field">
            <label className="config-checkbox">
              <input
                type="checkbox"
                checked={config.stopWhenNotMatch || false}
                onChange={(e) => update({ stopWhenNotMatch: e.target.checked })}
              />
              客户不再符合条件时提前停止执行
            </label>
          </div>
        </div>

        {/* 触发规则区 */}
        <div className="config-section">
          <div className="config-section-title">触发规则</div>
          <div className="config-tabs">
            {triggerTabs.map((tt) => (
              <button
                key={tt.key}
                type="button"
                className={`config-tab ${triggerType === tt.key ? 'config-tab--active' : ''}`}
                onClick={() => update({ triggerType: tt.key as SopNodeConfig['triggerType'] })}
              >
                {tt.label}
              </button>
            ))}
          </div>

          {triggerType === 'attribute_change' && (
            <div className="config-trigger-box">
              <div className="config-field">
                <label className="config-label">达成条件</label>
                <div className="config-condition-row">
                  <select className="config-select" style={{ flex: 1 }}>
                    <option value="">选择字段</option>
                    <option value="add_time">添加时间</option>
                    <option value="last_contact">最后联系时间</option>
                    <option value="tag_change">标签变更</option>
                  </select>
                  <select className="config-select" style={{ flex: 1 }}>
                    <option value="">选择条件</option>
                    <option value="within_days">在N天内</option>
                    <option value="after_days">N天后</option>
                    <option value="equals">等于</option>
                  </select>
                  <input
                    type="text"
                    className="config-input"
                    placeholder="值"
                    style={{ width: 80 }}
                  />
                </div>
              </div>
              <button type="button" className="config-add-condition">
                + 添加筛选条件
              </button>
            </div>
          )}

          {triggerType === 'timed' && (
            <div className="config-trigger-box">
              <div className="config-field">
                <label className="config-label">执行时间</label>
                <input
                  type="datetime-local"
                  className="config-input"
                  value={(triggerConfig.time as string) || ''}
                  onChange={(e) => update({ triggerConfig: { ...triggerConfig, time: e.target.value } })}
                />
              </div>
            </div>
          )}

          {triggerType === 'periodic' && (
            <div className="config-trigger-box">
              <div className="config-field">
                <label className="config-label">执行周期</label>
                <select
                  className="config-select"
                  value={(triggerConfig.period as string) || 'daily'}
                  onChange={(e) => update({ triggerConfig: { ...triggerConfig, period: e.target.value } })}
                >
                  {PERIOD_OPTIONS.map((po) => (
                    <option key={po.value} value={po.value}>
                      {po.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="config-field">
                <label className="config-label">执行时间</label>
                <input
                  type="time"
                  className="config-input"
                  value={(triggerConfig.runTime as string) || ''}
                  onChange={(e) => update({ triggerConfig: { ...triggerConfig, runTime: e.target.value } })}
                />
              </div>
            </div>
          )}

          {triggerType === 'special' && (
            <div className="config-trigger-box">
              <div className="config-field">
                <label className="config-label">场景类型</label>
                <select className="config-select">
                  <option value="">请选择特殊场景</option>
                  <option value="birthday">生日</option>
                  <option value="member_anniversary">会员周年</option>
                  <option value="first_purchase">首次购买</option>
                </select>
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }

  const renderMessage = () => {
    const contentType = (config.contentType as string) || 'text'
    return (
      <div className="flow-config-content">
        <div className="config-section">
          <div className="config-section-title">发送内容</div>
          <div className="config-tabs">
            {CONTENT_TABS.map((ct) => (
              <button
                key={ct.key}
                type="button"
                className={`config-tab ${contentType === ct.key ? 'config-tab--active' : ''}`}
                onClick={() => update({ contentType: ct.key as SopNodeConfig['contentType'] })}
              >
                {ct.label}
              </button>
            ))}
          </div>
          {contentType === 'text' && (
            <div className="config-field">
              <textarea
                className="config-textarea"
                rows={6}
                placeholder="输入消息文本内容..."
                value={(config.content as string) || ''}
                onChange={(e) => update({ content: e.target.value })}
              />
            </div>
          )}
          {contentType !== 'text' && (
            <div className="config-field">
              <div className="config-placeholder-upload">
                <p>点击或拖拽上传{CONTENT_TABS.find((t) => t.key === contentType)?.label}文件</p>
              </div>
            </div>
          )}
          <button type="button" className="config-add-condition">
            + 添加群发内容
          </button>
        </div>
      </div>
    )
  }

  const renderAttr = () => (
    <div className="flow-config-content">
      <div className="config-section">
        <div className="config-section-title">修改客户标签</div>
        <div className="config-field">
          <label className="config-label">添加标签</label>
          <select className="config-select" multiple size={4}>
            <option value="tag-1">高意向</option>
            <option value="tag-2">价格咨询</option>
            <option value="tag-3">预约演示</option>
            <option value="tag-intent-1">高</option>
            <option value="tag-intent-2">中</option>
            <option value="tag-intent-3">低</option>
          </select>
        </div>
        <div className="config-field">
          <label className="config-label">移除标签</label>
          <select className="config-select" multiple size={4}>
            <option value="tag-1">高意向</option>
            <option value="tag-2">价格咨询</option>
            <option value="tag-3">预约演示</option>
          </select>
        </div>
      </div>
    </div>
  )

  const renderRobot = () => (
    <div className="flow-config-content">
      <div className="config-section">
        <div className="config-section-title">机器人托管</div>
        <div className="config-field">
          <label className="config-label">托管机器人</label>
          <select
            className="config-select"
            value={(config.robotId as string) || ''}
            onChange={(e) => update({ robotId: e.target.value })}
          >
            <option value="">请选择机器人托管</option>
            <option value="yefengqiu">野风秋大健康机器人</option>
            <option value="fanfuni">梵芙尼美妆销售机器人</option>
          </select>
        </div>
      </div>
    </div>
  )

  const renderRunRobot = () => (
    <div className="flow-config-content">
      <div className="config-section">
        <div className="config-section-title">运行机器人</div>
        <div className="config-field">
          <label className="config-label">运行机器人</label>
          <select
            className="config-select"
            value={(config.runRobotId as string) || ''}
            onChange={(e) => update({ runRobotId: e.target.value })}
          >
            <option value="">请选择运行机器人</option>
            <option value="yefengqiu">野风秋大健康机器人</option>
            <option value="fanfuni">梵芙尼美妆销售机器人</option>
          </select>
        </div>
      </div>
    </div>
  )

  const renderDelay = () => (
    <div className="flow-config-content">
      <div className="config-section">
        <div className="config-section-title">延迟时间</div>
        <div className="config-field">
          <label className="config-label">延迟时长</label>
          <div className="config-input-row">
            <input
              type="number"
              className="config-input"
              style={{ width: 100 }}
              min={0}
              step={0.5}
              placeholder="0"
              value={config.hours ?? ''}
              onChange={(e) => update({ hours: parseFloat(e.target.value) || 0 })}
            />
            <span className="config-input-suffix">小时</span>
          </div>
        </div>
      </div>
    </div>
  )

  const renderContent = () => {
    switch (node.type) {
      case 'settings':
      case 'group-settings':
        return renderSettings()
      case 'message':
        return renderMessage()
      case 'attr':
        return renderAttr()
      case 'robot':
        return renderRobot()
      case 'runRobot':
        return renderRunRobot()
      case 'delay':
        return renderDelay()
      default:
        return <div className="flow-config-empty"><p>未知节点类型</p></div>
    }
  }

  return (
    <div className="flow-config-panel">
      <div className="flow-config-header">
        <h3>{node.type === 'settings' || node.type === 'group-settings' ? '流程设置' : '节点配置'}</h3>
      </div>
      {renderContent()}
    </div>
  )
}
