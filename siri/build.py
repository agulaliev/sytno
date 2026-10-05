#!/usr/bin/env python3
"""Собирает и подписывает Команды для Siri. Запуск на Mac: python3 siri/build.py"""
import os, plistlib, subprocess, tempfile, uuid

HERE = os.path.dirname(os.path.abspath(__file__))


def uid():
    return str(uuid.uuid4()).upper()


def act(ident, params=None, u=None):
    p = dict(params or {})
    if u:
        p['UUID'] = u
    return {'WFWorkflowActionIdentifier': ident, 'WFWorkflowActionParameters': p}


def out(u, name, prop=None, time=False):
    v = {'Type': 'ActionOutput', 'OutputUUID': u, 'OutputName': name}
    ag = []
    if prop:
        ag.append({'Type': 'WFPropertyVariableAggrandizement', 'PropertyName': prop})
    if time:
        ag.append({'Type': 'WFDateFormatVariableAggrandizement', 'WFDateFormatStyle': 'None',
                   'WFTimeFormatStyle': 'Short', 'WFRelativeDateFormatStyle': 'None', 'WFISO8601IncludeTime': False})
    if ag:
        v['Aggrandizements'] = ag
    return v


def text(*parts):
    s, att = '', {}
    for p in parts:
        if isinstance(p, str):
            s += p
        else:
            att['{%d, 1}' % (len(s.encode('utf-16-le')) // 2)] = p
            s += '￼'
    return {'Value': {'string': s, 'attachmentsByRange': att}, 'WFSerializationType': 'WFTextTokenString'}


def ref(v):
    return {'Value': v, 'WFSerializationType': 'WFTextTokenAttachment'}


def find_events(u, date_tmpl, title_prefix, limit=None):
    p = {
        'WFContentItemFilter': {
            'Value': {
                'WFActionParameterFilterPrefix': 1,
                'WFContentPredicateBoundedDate': False,
                'WFActionParameterFilterTemplates': [
                    dict(date_tmpl, Property='Start Date', Removable=True),
                    {'Operator': 8, 'Property': 'Title', 'Removable': True, 'Values': {'String': title_prefix}},
                ],
            },
            'WFSerializationType': 'WFContentPredicateTableTemplate',
        },
        'WFContentItemSortProperty': 'Start Date',
        'WFContentItemSortOrder': 'Oldest First',
    }
    if limit:
        p['WFContentItemLimitEnabled'] = True
        p['WFContentItemLimitNumber'] = limit
    return act('is.workflow.actions.filter.calendarevents', p, u)


TODAY = {'Operator': 1002, 'Values': {}}
NEXT_WEEK = {'Operator': 1000, 'Values': {'Number': 7, 'Unit': 16}}


def if_any(var, then, otherwise):
    g = uid()
    return ([act('is.workflow.actions.conditional', {'GroupingIdentifier': g, 'WFControlFlowMode': 0, 'WFCondition': 100,
                                                     'WFInput': {'Type': 'Variable', 'Variable': ref(var)}})]
            + then
            + [act('is.workflow.actions.conditional', {'GroupingIdentifier': g, 'WFControlFlowMode': 1})]
            + otherwise
            + [act('is.workflow.actions.conditional', {'GroupingIdentifier': g, 'WFControlFlowMode': 2})])


def say(*parts):
    return act('is.workflow.actions.showresult', {'Text': text(*parts)})


def first_line(src_var, u_split, u_first):
    return [act('is.workflow.actions.text.split', {'text': text(src_var), 'WFTextSeparator': 'New Lines'}, u_split),
            act('is.workflow.actions.getitemfromlist', {'WFInput': ref(out(u_split, 'Split Text')), 'WFItemSpecifier': 'First Item'}, u_first)]


def dinner():
    e, sp, fl = uid(), uid(), uid()
    ev = 'Calendar Events'
    return [find_events(e, TODAY, 'Ужин', 1)] + if_any(
        out(e, ev),
        first_line(out(e, ev, 'Notes'), sp, fl) + [
            say(out(e, ev, 'Title'), '. Начать в ', out(e, ev, 'Start Date', time=True), '. ', out(fl, 'Item from List'))],
        [say('На сегодня ужина в календаре нет. Открой «Сытно» и нажми «Добавить неделю в Календарь».')])


def shopping_today():
    e = uid()
    ev = 'Calendar Events'
    return [find_events(e, TODAY, 'Купить', 1)] + if_any(
        out(e, ev),
        [say(out(e, ev, 'Title'), ':\n', out(e, ev, 'Notes'))],
        [say('Сегодня ничего докупать не нужно.')])


def to_reminders():
    e, c, sp = uid(), uid(), uid()
    ev = 'Calendar Events'
    loop = uid()
    body = [
        act('is.workflow.actions.text.combine', {'text': ref(out(e, ev, 'Notes')), 'WFTextSeparator': 'New Lines'}, c),
        act('is.workflow.actions.text.split', {'text': text(out(c, 'Combined Text')), 'WFTextSeparator': 'New Lines'}, sp),
        act('is.workflow.actions.repeat.each', {'GroupingIdentifier': loop, 'WFControlFlowMode': 0, 'WFInput': ref(out(sp, 'Split Text'))}),
        act('is.workflow.actions.addnewreminder', {'WFCalendarItemTitle': text({'Type': 'Variable', 'VariableName': 'Repeat Item'})}),
        act('is.workflow.actions.repeat.each', {'GroupingIdentifier': loop, 'WFControlFlowMode': 2}),
        say('Готово: покупки на неделю добавлены в Напоминания.'),
    ]
    return [find_events(e, NEXT_WEEK, 'Купить')] + if_any(
        out(e, ev), body,
        [say('В календаре нет покупок на ближайшую неделю. Открой «Сытно» и нажми «Добавить неделю в Календарь».')])


SHORTCUTS = {
    'Что на ужин': (dinner, 59511, 4282601983),
    'Что купить': (shopping_today, 59511, 4251333119),
    'Покупки в Напоминания': (to_reminders, 59511, 4292093695),
}


def build(name, fn, glyph, color):
    wf = {
        'WFWorkflowClientVersion': '2302.0.4', 'WFWorkflowMinimumClientVersion': 900, 'WFWorkflowMinimumClientVersionString': '900',
        'WFWorkflowIcon': {'WFWorkflowIconStartColor': color, 'WFWorkflowIconGlyphNumber': glyph},
        'WFWorkflowImportQuestions': [], 'WFWorkflowTypes': [], 'WFWorkflowInputContentItemClasses': [],
        'WFWorkflowOutputContentItemClasses': [], 'WFWorkflowHasShortcutInputVariables': False,
        'WFWorkflowActions': fn(),
    }
    with tempfile.NamedTemporaryFile(suffix='.shortcut', delete=False) as f:
        plistlib.dump(wf, f, fmt=plistlib.FMT_BINARY)
        raw = f.name
    dst = os.path.join(HERE, name + '.shortcut')
    subprocess.run(['shortcuts', 'sign', '--mode', 'anyone', '--input', raw, '--output', dst], check=True)
    os.unlink(raw)
    print('ok', dst)


if __name__ == '__main__':
    for n, (fn, g, c) in SHORTCUTS.items():
        build(n, fn, g, c)
