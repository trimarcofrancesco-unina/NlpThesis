from datetime import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QLineEdit, QDoubleSpinBox, \
    QSizePolicy, QSpacerItem, QGraphicsOpacityEffect

from model.answer_model import Answer


class TeacherStudentAnswerPreviewItem(QWidget):
    def __init__(self, db_worker, authorized_user, answer: Answer, evaluated):
        super().__init__()

        self.db_worker = db_worker
        self.authorized_user = authorized_user
        self.answer = answer
        self.evaluated = evaluated

        self.__initUi()

    def convert_datetime(self, datetime_str):
        datetime_obj = datetime.fromisoformat(datetime_str)
        return datetime_obj.strftime("%d/%m/%Y %H:%M")

    def __initUi(self):
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("answer_preview_item_container")
        self.setStyleSheet('''
                    #answer_preview_item_container {
                        background-color: rgba(0, 0, 0, 0.1);
                        border-radius: 20px;
                    }''')

        lay = QVBoxLayout()
        lay.setSpacing(0)

        label_id_studente = QLabel("Studente: " + self.answer.id_autore)
        label_id_studente.setStyleSheet('''
                                            QLabel {
                                                font-size: 12px; 
                                                font-weight: bold;
                                            }
                                        ''')

        label_data_risposta = QLabel(self.convert_datetime(self.answer.data_creazione))
        label_data_risposta.setStyleSheet('''
                                            QLabel {
                                                font-size: 10px; 
                                            }
                                        ''')
        opacity_effect = QGraphicsOpacityEffect()
        opacity_effect.setOpacity(0.6)  # Imposta l'opacità al 60%
        label_data_risposta.setGraphicsEffect(opacity_effect)

        answer_label = QLabel(self.answer.risposta)
        answer_label.setWordWrap(True)

        risultatoLayout = QHBoxLayout()

        if not self.evaluated:
            self.label_risultato = QLabel(str(self.answer.voto_predetto))
            policy = self.label_risultato.sizePolicy()
            policy.setHorizontalPolicy(QSizePolicy.Expanding)
            self.label_risultato.setSizePolicy(policy)

            if self.answer.voto_predetto >= 3:
                self.label_risultato.setStyleSheet('''
                                    QLabel {
                                        font-size: 12px; 
                                        font-weight: bold;
                                        color: #32a852;
                                    }
                                ''')
            else:
                self.label_risultato.setStyleSheet('''
                                    QLabel {
                                        font-size: 12px; 
                                        font-weight: bold;
                                        color: #a83232;
                                    }
                                ''')

            self.votoCustomSpinBox = QDoubleSpinBox()
            self.votoCustomSpinBox.setValue(self.answer.voto_predetto)
            self.votoCustomSpinBox.setSingleStep(0.50)
            self.votoCustomSpinBox.setMinimum(0)
            self.votoCustomSpinBox.setMaximum(5)

            assegnaVotoBtn = QPushButton("Assegna voto")

            confermaVotoLayout = QHBoxLayout()

            lay.addWidget(label_id_studente)
            lay.addWidget(label_data_risposta)
            lay.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Expanding))
            lay.addWidget(answer_label)
            lay.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Expanding))

            risultatoLayout.addWidget(QLabel("Risultato predetto: "))
            risultatoLayout.addWidget(self.label_risultato)
            lay.addLayout(risultatoLayout)
            confermaVotoLayout.addWidget(self.votoCustomSpinBox)
            confermaVotoLayout.addWidget(assegnaVotoBtn)
            lay.addLayout(confermaVotoLayout)

            assegnaVotoBtn.clicked.connect(self.__assignVote)
        else:
            label_risultato = QLabel(str(self.answer.voto_docente))
            policy = label_risultato.sizePolicy()
            policy.setHorizontalPolicy(QSizePolicy.Expanding)
            label_risultato.setSizePolicy(policy)

            if self.answer.voto_docente >= 3:
                label_risultato.setStyleSheet('''
                                                QLabel {
                                                    font-size: 12px; 
                                                    font-weight: bold;
                                                    color: #32a852;
                                                }
                                            ''')
            else:
                label_risultato.setStyleSheet('''
                                                QLabel {
                                                    font-size: 12px; 
                                                    font-weight: bold;
                                                    color: #a83232;
                                                }
                                            ''')

            lay.addWidget(label_id_studente)
            lay.addWidget(label_data_risposta)
            lay.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Expanding))
            lay.addWidget(answer_label)
            lay.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Expanding))

            voto_finale_lbl = QLabel("Voto finale: ")
            risultatoLayout.addWidget(voto_finale_lbl)
            risultatoLayout.addWidget(label_risultato)
            lay.addLayout(risultatoLayout)

        self.setLayout(lay)

    def __assignVote(self):
        if self.db_worker is not None:
            self.db_worker.assign_vote(self.answer, self.votoCustomSpinBox.value())
