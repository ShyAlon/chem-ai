"""Deterministic semantic extraction: mentions become scoped relationships and facts."""
from .activities import activity
from .definitions import read_data
from .matching import compile_terms, find_terms
from .normalization import words
from .lexicon import CLEANING_TERMS
from .situation_models import Situation, SituationEntity, SituationFact, SituationRelation, SituationAction, TextSpan

CONFIG = read_data('situation.json')
RISK_TERMS = {key: compile_terms({key: rule['terms']}) for key, rule in CONFIG['risk_facts'].items()}


def predicate(token):
    while token.head != token and token.pos_ not in {'VERB', 'AUX'}:
        token = token.head
    return token


def ancestors(token):
    result = [token]
    while token.head != token:
        token = token.head
        result.append(token)
    return result


def span(token) -> TextSpan:
    return TextSpan(start=token.idx, end=token.idx + len(token.text), text=token.text)


def positions(text, token):
    return set(range(len(words(text[:token.idx])), len(words(text[:token.idx + len(token.text)]))))


def context(token):
    verb = predicate(token)
    chain = ancestors(token)
    scope = [node for node in chain if node == token or node.pos_ in {'VERB', 'AUX', 'ADP'}]
    negated = any(node.lemma_.casefold() == 'without' or any(child.dep_ == 'neg' or child.lower_ in {'never', 'no'} for child in node.children) for node in scope)
    uncertain = any(node.lower_ in CONFIG['uncertainty_terms'] for node in verb.sent)
    question = any(node.text == '?' for node in verb.sent) or verb.sent[0].lower_ in {'how', 'can', 'could', 'should', 'would'}
    proposed = question or any(node.lemma_ in CONFIG['proposal_actions'] for node in chain) or any(child.lower_ in {'will', 'might', 'may', 'should', 'could'} for node in chain for child in node.children)
    has_subject = any(child.dep_ in {'nsubj','nsubjpass'} for child in verb.children)
    present_aux = any(child.lemma_ == 'be' and 'Pres' in child.morph.get('Tense') for child in verb.children)
    past = ('Past' in verb.morph.get('Tense') and has_subject and not present_aux) or any(node.lemma_ == 'after' for node in chain)
    return verb, negated, uncertain, proposed, past


def build_situation(text, doc, targets, groups, intent, task_positions) -> Situation:
    with activity('normalization', 'situation.build', schema_version='1') as operation:
        frame = Situation(original_text=text, english_text=text)
        normalized = words(text)
        token_map = {}
        for token in doc:
            for index in positions(text, token):
                token_map[index] = token
        roots, spans, entity_positions = {}, {}, {}
        group_kinds = {'objects':'object', 'categories':'object', 'substrates':'material', 'finishes':'finish', 'devices':'device', 'supplies':'product', 'exclusions':'condition'}
        for group, matches in groups.items():
            for match in matches:
                matched = [token_map[index] for index in sorted(match.positions) if index in token_map]
                if not matched:
                    continue
                start, end = matched[0].idx, matched[-1].idx + len(matched[-1].text)
                phrase = doc.char_span(start, end, alignment_mode='expand')
                entity = SituationEntity(id=f'e{len(frame.entities)}', kind=group_kinds[group], value=match.value,
                    role='context' if group in {'objects','categories','devices'} else 'attribute',
                    evidence=TextSpan(start=start, end=end, text=text[start:end]))
                if group == 'supplies':
                    entity.role = 'supply'
                    if entity.value in CONFIG['tool_ids']:
                        entity.kind = 'tool'
                frame.entities.append(entity)
                roots[entity.id], spans[entity.id], entity_positions[entity.id] = phrase.root, phrase, set(match.positions)
        objects = [item for item in frame.entities if item.kind == 'object']
        # Prefer grammatical request patients. Historical patients stay context.
        active_targets = []
        request_predicates = set()
        for target in targets:
            token = doc[target.head_index]
            verb, negative, uncertain, proposed, past = context(token)
            modality = 'negated' if negative else 'uncertain' if uncertain else 'historical' if past and not proposed else 'requested'
            action_intent = 'clean' if set(words(verb.lemma_)).intersection(words(' '.join(CLEANING_TERMS))) else intent or 'unknown'
            action = SituationAction(intent=action_intent, verb=verb.lemma_, modality=modality, evidence=span(verb))
            frame.actions.append(action)
            if modality != 'requested':
                continue
            request_predicates.add(verb.i)
            overlapping = [item for item in objects if item.evidence.start < target.end and target.start < item.evidence.end]
            reserved = [item for item in frame.entities if item.kind in {'material','finish','device','product','tool'} and item.evidence.start <= token.idx < item.evidence.end]
            if overlapping:
                active_targets.extend(overlapping)
            elif target.entity and not reserved:
                entity = SituationEntity(id=f'e{len(frame.entities)}', kind='object', value=target.lemma, role='target',
                    evidence=TextSpan(start=target.start, end=target.end, text=text[target.start:target.end]))
                frame.entities.append(entity)
                roots[entity.id], entity_positions[entity.id] = token, positions(text, token)
                active_targets.append(entity)
            frame.covered_positions.extend(target.context_positions)
            if target.problem:
                problem_token = next(node for node in doc if node.lemma_ == target.problem and positions(text, node).intersection(target.context_positions))
                problem = SituationEntity(id=f'e{len(frame.entities)}', kind='problem', value=target.problem, role='problem', evidence=span(problem_token))
                frame.entities.append(problem)
                for affected in active_targets:
                    frame.relations.append(SituationRelation(subject=problem.id, predicate='affects', object=affected.id, evidence=problem.evidence))
        if not active_targets:
            # Fragments/state descriptions and bounded pronoun recovery.
            predicates = {predicate(token_map[index]).i for index in task_positions if index in token_map}
            active_targets = [item for item in objects if predicate(roots[item.id]).i in predicates and not any(node.dep_ == 'prep' and node.lemma_ in CONFIG['context_prepositions'] for node in ancestors(roots[item.id]))] if not frame.actions or any(action.modality == 'requested' for action in frame.actions) else []
            if not active_targets and any(action.modality == 'requested' for action in frame.actions) and len({item.value for item in objects}) == 1 and any(token.lower_ in {'it','this'} and token.dep_ in {'dobj','obj'} for token in doc):
                active_targets = objects[:1]
            # A dictionary-only fragment can still be inspected; it grants no new policy scope.
            if not active_targets and not targets and not frame.actions and len(list(doc.sents)) == 1:
                active_targets = objects
        frame.target_ids = list(dict.fromkeys(item.id for item in active_targets))
        for item in frame.targets():
            item.role = 'target'
        if len(frame.target_ids) > 1:
            frame.ambiguities.append('target')
        selected = frame.targets()
        for action in frame.actions:
            if action.modality == 'requested':
                action.targets = frame.target_ids.copy()
        requested_sentences = {roots[item.id].sent.start for item in selected}
        requested_sentences.update(doc[index].sent.start for index in request_predicates)
        # Ignore unrelated clauses for supply validation, but retain their entities/facts.
        for sentence in doc.sents:
            if requested_sentences and sentence.start not in requested_sentences:
                for token in sentence:
                    frame.ignored_positions.extend(positions(text, token))
        for item in objects:
            if item.id in frame.target_ids:
                continue
            token = roots[item.id]
            for node in ancestors(token):
                if node.dep_ == 'prep' and node.lemma_ in CONFIG['context_prepositions']:
                    for child in node.subtree:
                        frame.ignored_positions.extend(positions(text, child))
                    break
        def attach_subject(token, *, product=False, attribute=False):
            chain = ancestors(token)
            for target in selected:
                target_root = roots[target.id]
                anchor = target_root.head if target_root.dep_ == 'appos' else target_root
                if target_root in chain or (attribute and anchor in chain):
                    return target.id
                # Lexical head spans such as "screen protector" include the target alias.
                if target.evidence.start <= token.idx < target.evidence.end:
                    return target.id
            if attribute:
                known = {index for entity in frame.entities if entity.kind in {'material','finish','device'} or entity.id in frame.target_ids for index in entity_positions.get(entity.id, [])}
                for target in selected:
                    target_root = roots[target.id]
                    between = [node for node in doc if token.idx < node.idx < target_root.idx]
                    if token.sent == target_root.sent and token.idx < target_root.idx and all(positions(text, node) <= known or node.pos_ == 'DET' for node in between):
                        return target.id
            if product:
                verb = predicate(token)
                local_objects = [item for item in objects if predicate(roots[item.id]) == verb]
                if local_objects:
                    candidates = [target for target in selected if any(item.value == target.value for item in local_objects)]
                    return candidates[0].id if len(candidates) == 1 else local_objects[0].id
                if len(selected) == 1:
                    return selected[0].id
            # Attributes of context entities must not leak onto the request target.
            for item in objects:
                if roots[item.id] in chain:
                    return item.id
            return None
        for item in frame.entities.copy():
            if item.kind in {'object','problem'} or item.id not in roots:
                continue
            token = roots[item.id]
            verb, negative, uncertain, proposed, past = context(token)
            product = item.kind in {'product','tool'}
            subject = attach_subject(token, product=product, attribute=item.kind in {'material','finish','device','condition'})
            if subject is None:
                continue
            name = {'material':'material','finish':'finish','device':'device','product':'supplies','tool':'supplies','condition':'damage'}[item.kind]
            if product and verb.lemma_ in CONFIG['availability_actions'] and not proposed:
                name = 'available_supplies'
            # Products in a historical/negated clause aren't proposed cleaning supplies.
            time = 'past' if past and not proposed else 'proposed' if product else 'current'
            polarity = 'uncertain' if uncertain else 'negated' if negative else 'affirmed'
            fact = SituationFact(subject=subject, predicate=name, value=item.value, polarity=polarity, time=time, evidence=[item.evidence, span(verb)])
            frame.facts.append(fact)
            frame.relations.append(SituationRelation(subject=item.id, predicate='used_on' if product else 'attribute_of', object=subject, evidence=item.evidence))
            if subject in frame.target_ids and (not product or (not past and not negative)):
                frame.covered_positions.extend(entity_positions[item.id])
            if product and (past or negative or name == 'available_supplies' or subject not in frame.target_ids):
                frame.ignored_positions.extend(entity_positions[item.id])
                # Negation grammar is understood, not an unexplained supply name.
                if negative:
                    for node in ancestors(token):
                        if node.lower_ == 'without' or node.dep_ == 'neg':
                            frame.ignored_positions.extend(positions(text, node))
        # Condition facts are scoped by their own clause and explicit fixture references.
        for fact_name, terms in RISK_TERMS.items():
            rule = CONFIG['risk_facts'][fact_name]
            for match in find_terms(normalized, terms):
                matched = [token_map[index] for index in sorted(match.positions) if index in token_map]
                if not matched:
                    continue
                phrase = doc.char_span(matched[0].idx, matched[-1].idx + len(matched[-1].text), alignment_mode='expand')
                token = phrase.root
                verb, negative, uncertain, proposed, past = context(token)
                if any(child.lower_ == 'no' for node in phrase for child in node.children):
                    negative = True
                subject = attach_subject(token, product=True)
                if subject is None:
                    continue
                local_fixture = any(predicate(roots[item.id]) == verb for item in objects)
                history_known = not rule['requires_history'] or (past and not proposed and verb.lemma_ in CONFIG['history_actions']) or (not proposed and local_fixture and verb.lemma_ in CONFIG['presence_actions'])
                polarity = 'uncertain' if uncertain or not history_known else 'affirmed'
                frame.facts.append(SituationFact(subject=subject, predicate=fact_name, value=negative,
                    polarity=polarity, time='past' if past else 'current' if history_known else 'unknown',
                    evidence=[TextSpan(start=phrase.start_char, end=phrase.end_char, text=phrase.text), span(verb)]))
                if subject in frame.target_ids and polarity == 'affirmed':
                    # The full factual clause is recorded; don't treat its grammar as unknown supplies.
                    for node in verb.subtree:
                        if node.sent.start != doc[0].sent.start or predicate(node).i not in request_predicates:
                            frame.ignored_positions.extend(positions(text, node))
        for item in selected:
            frame.covered_positions.extend(entity_positions[item.id])
        for name in {'material','finish','chemical_free','isolated_intact'}:
            if len(frame.values(name)) > 1:
                frame.ambiguities.append(name)
        frame.covered_positions = sorted(set(frame.covered_positions))
        frame.ignored_positions = sorted(set(frame.ignored_positions))
        operation.details.update(targets=len(frame.target_ids), entities=len(frame.entities), facts=len(frame.facts), ambiguities=', '.join(frame.ambiguities))
        operation.debug['relations'] = [f'{item.subject} {item.predicate} {item.object}' for item in frame.relations]
        return frame
